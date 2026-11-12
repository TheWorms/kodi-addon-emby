# Gnu General Public License - see LICENSE.TXT
"""v1.22.0 : diagnostic de la qualite automatique et du transcodage.

- Au lancement : une ligne de journal dit ce que vaut la video (resolution,
  codec, debit), la limite appliquee et la decision (lecture directe ou
  transcodage) avec les raisons donnees par Emby.
- Pendant un transcodage : apres quelques secondes, EmbyCon demande au
  serveur a quelle vitesse il transcode. S'il produit moins d'images par
  seconde que la video n'en contient, la lecture va saccader quelle que soit
  la connexion : une notification le signale (cas typique d'un film 4K HDR
  sur un serveur sans transcodage materiel).
"""

from __future__ import annotations

import json
import threading
from urllib.parse import parse_qs

from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)

CHECK_DELAY = 25  # secondes de lecture reelle avant la mesure
START_TIMEOUT = 120  # secondes au plus pour que la video demarre
SLOW_RATIO = 0.9  # moins de 90 % des images/s de la video = trop lent


def source_video(media_source: dict) -> dict:
    for stream in media_source.get("MediaStreams") or []:
        if stream.get("Type") == "Video":
            return stream
    return {}


def source_fps(media_source: dict) -> float:
    video = source_video(media_source)
    for key in ("RealFrameRate", "AverageFrameRate"):
        try:
            value = float(video.get(key) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value
    return 0.0


def _kbps(bits_per_second) -> str:
    try:
        return (
            "{0:,}".format(int(int(bits_per_second) / 1000)).replace(",", " ") + " kb/s"
        )
    except (TypeError, ValueError):
        return "? kb/s"


def describe_source(media_source: dict) -> str:
    """« 3840x2160 HEVC HDR10 · 62 400 kb/s · 23.976 i/s »."""
    video = source_video(media_source)
    parts = []
    if video.get("Width") and video.get("Height"):
        parts.append("%sx%s" % (video.get("Width"), video.get("Height")))
    codec = str(video.get("Codec") or "").upper()
    video_range = str(video.get("VideoRange") or "")
    if video_range and video_range.upper() != "SDR":
        codec = (codec + " " + video_range).strip()
    if codec:
        parts.append(codec)
    parts.append(_kbps(media_source.get("Bitrate") or video.get("BitRate")))
    fps = source_fps(media_source)
    if fps:
        parts.append(("%.3f" % fps).rstrip("0").rstrip(".") + " i/s")
    return " · ".join(parts)


def transcode_reasons(media_source: dict) -> str:
    """Raisons du transcodage donnees par Emby (dans TranscodingUrl)."""
    url = str(media_source.get("TranscodingUrl") or "")
    if "?" not in url:
        return ""
    params = parse_qs(url.split("?", 1)[1])
    return ",".join(params.get("TranscodeReasons", []))


def decision_line(
    name: str, media_source: dict, limit_kbps: str, auto: bool, playback_type: str
) -> str:
    reasons = transcode_reasons(media_source) if playback_type == "Transcode" else ""
    line = "Lecture « %s » : %s ; limite %s kb/s (%s) -> %s" % (
        name,
        describe_source(media_source),
        limit_kbps,
        "qualité auto" if auto else "débit fixe",
        playback_type,
    )
    if reasons:
        line += " (raisons Emby : %s)" % reasons
    return line


def is_too_slow(transcoding_info: dict, fps: float) -> bool:
    """Le serveur transcode-t-il moins vite que la video ne defile ?

    Un transcodage mis en pause par le serveur (il a assez d'avance) n'est
    jamais considere comme lent.
    """
    info = transcoding_info or {}
    if info.get("CurrentThrottle") or info.get("IsVideoDirect"):
        return False
    try:
        produced = float(info.get("Framerate") or 0)
    except (TypeError, ValueError):
        return False
    return produced > 0 and fps > 0 and produced < fps * SLOW_RATIO


def describe_transcoding(info: dict) -> str:
    parts = []
    if info.get("Width") and info.get("Height"):
        parts.append("%sx%s" % (info.get("Width"), info.get("Height")))
    if info.get("VideoCodec"):
        parts.append(
            str(info.get("VideoCodec")).upper()
            + (" (copie)" if info.get("IsVideoDirect") else "")
        )
    if info.get("Bitrate"):
        parts.append(_kbps(info.get("Bitrate")))
    if info.get("Framerate"):
        parts.append("%s i/s produites" % info.get("Framerate"))
    hardware = [
        label
        for key, label in (
            ("VideoDecoderIsHardware", "décodage matériel"),
            ("VideoEncoderIsHardware", "encodage matériel"),
        )
        if info.get(key)
    ]
    if hardware:
        parts.append(" + ".join(hardware))
    elif "VideoDecoderIsHardware" in info or "VideoEncoderIsHardware" in info:
        parts.append("transcodage logiciel")
    try:
        if info.get("CurrentCpuUsage") is not None:
            parts.append("CPU serveur %d %%" % round(float(info["CurrentCpuUsage"])))
    except (TypeError, ValueError):
        pass
    if info.get("CurrentThrottle"):
        parts.append("en avance (pause)")
    reasons = info.get("TranscodeReasons") or []
    if reasons:
        parts.append("raisons : " + ",".join(str(r) for r in reasons))
    return " · ".join(parts)


def _session_transcoding(sessions, item_id: str) -> dict:
    """TranscodingInfo de la session qui lit cet element (sinon la premiere)."""
    if not isinstance(sessions, list):
        return {}
    found = {}
    for session in sessions:
        if not isinstance(session, dict) or not session.get("TranscodingInfo"):
            continue
        playing = (session.get("NowPlayingItem") or {}).get("Id")
        if str(playing) == str(item_id):
            return session["TranscodingInfo"]
        found = found or session["TranscodingInfo"]
    return found


def report_transcoding(item_id: str, fps: float, name: str) -> bool:
    """Interroge le serveur sur le transcodage en cours et le journalise.

    Renvoie True si le serveur est trop lent (une notification est affichee).
    """
    import xbmcgui

    from .clientinfo import ClientInformation
    from .downloadutils import DownloadUtils
    from .kodi_utils import HomeWindow
    from .translation import string_load

    if HomeWindow().get_property("currently_playing_id") != str(item_id):
        return False
    try:
        device_id = ClientInformation().get_device_id()
        raw = DownloadUtils().download_url(
            "{server}/emby/Sessions?DeviceId=%s&format=json" % device_id, suppress=True
        )
        info = _session_transcoding(json.loads(raw) if raw else [], item_id)
    except Exception as err:
        log.error("Transcodage : etat du serveur illisible ({0})", err)
        return False
    if not info:
        log.info("Transcodage « {0} » : pas d'information du serveur", name)
        return False
    log.info("Transcodage « {0} » : {1}", name, describe_transcoding(info))
    if not is_too_slow(info, fps):
        return False
    produced = float(info.get("Framerate") or 0)
    log.info(
        "Transcodage « {0} » : serveur trop lent ({1:.0f} i/s pour {2:.0f})",
        name,
        produced,
        fps,
    )
    xbmcgui.Dialog().notification(
        string_load(30899),
        string_load(30900).format(int(produced), int(round(fps))),
        icon="special://home/addons/plugin.video.embycon/icon-addon.png",
        time=8000,
    )
    return True


def video_running(is_playing_video: bool, position: float, paused: bool) -> bool:
    """La video defile-t-elle vraiment (demarrage et reprise termines) ?"""
    return bool(is_playing_video) and position > 0 and not paused


def _check(item_id: str, fps: float, name: str) -> None:
    import xbmc

    monitor = xbmc.Monitor()
    player = xbmc.Player()
    # v1.22.4 : attendre que la video defile (2 min au plus) ; mesurer pendant
    # le demarrage ou juste apres une reprise donnait de fausses alertes
    for _ in range(START_TIMEOUT):
        if monitor.waitForAbort(1):
            return
        try:
            running = video_running(
                player.isPlayingVideo(),
                player.getTime(),
                bool(xbmc.getCondVisibility("Player.Paused")),
            )
        except Exception:
            running = False
        if running:
            break
    else:
        return
    if monitor.waitForAbort(CHECK_DELAY):
        return
    report_transcoding(item_id, fps, name)


def check_transcode_later(item_id: str, media_source: dict, name: str) -> None:
    """Lance la verification de la vitesse du transcodage en arriere-plan."""
    threading.Thread(
        target=_check, args=(item_id, source_fps(media_source), name), daemon=True
    ).start()
