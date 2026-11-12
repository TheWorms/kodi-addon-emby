"""Tests v1.22.0 : lecture reduite (transcodage) — pistes automatiques et
diagnostic de la qualite automatique."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.play_utils as pu  # noqa: E402
import lib.track_choice as tc  # noqa: E402
import lib.transcode_check as tchk  # noqa: E402

NAMES = {"fre": "Français", "eng": "Anglais", "jpn": "Japonais"}
WORDS = {
    "unknown": "Langue inconnue",
    "default": "défaut",
    "forced": "forcés",
    "external": "externe",
    "none": "Aucun sous-titre",
}

# film UHD typique : VO anglaise par defaut, VFF, commentaire, sous-titres
FILM = [
    {
        "Index": 0,
        "Type": "Video",
        "Codec": "hevc",
        "Width": 3840,
        "Height": 2160,
        "VideoRange": "HDR10",
        "RealFrameRate": 23.976,
        "BitRate": 62400000,
    },
    {
        "Index": 1,
        "Type": "Audio",
        "Language": "eng",
        "Codec": "truehd",
        "Channels": 8,
        "ChannelLayout": "7.1",
        "IsDefault": True,
    },
    {
        "Index": 2,
        "Type": "Audio",
        "Language": "fre",
        "Codec": "ac3",
        "Channels": 2,
        "Title": "VFQ",
    },
    {
        "Index": 3,
        "Type": "Audio",
        "Language": "fre",
        "Codec": "eac3",
        "Channels": 6,
        "Title": "VFF",
    },
    {
        "Index": 4,
        "Type": "Audio",
        "Language": "fre",
        "Codec": "ac3",
        "Channels": 6,
        "Title": "Commentaire du réalisateur",
    },
    {
        "Index": 5,
        "Type": "Subtitle",
        "Language": "fre",
        "Codec": "pgssub",
        "IsForced": True,
    },
    {"Index": 6, "Type": "Subtitle", "Language": "fre", "Codec": "pgssub"},
    {
        "Index": 7,
        "Type": "Subtitle",
        "Language": "eng",
        "Codec": "pgssub",
        "IsForced": True,
    },
    {
        "Index": 8,
        "Type": "Subtitle",
        "Language": "fre",
        "Codec": "srt",
        "IsExternal": True,
        "IsTextSubtitleStream": True,
        "SupportsExternalStream": True,
    },
]


# --- choix de la piste audio -----------------------------------------------------


def test_audio_dans_ma_langue_la_plus_riche_sans_commentaire() -> None:
    # VFF 5.1 plutot que VFQ stereo, jamais le commentaire
    assert tc.choose_audio(FILM, "fre", 1) == 3


def test_audio_piste_par_defaut_de_ma_langue_d_abord() -> None:
    pistes = [dict(s) for s in FILM]
    pistes[2]["IsDefault"] = True  # VFQ stereo marquee par defaut
    assert tc.choose_audio(pistes, "fre", 1) == 2


def test_audio_repli_sur_la_piste_par_defaut_du_serveur() -> None:
    assert tc.choose_audio(FILM, "jpn", 1) == 1
    assert tc.choose_audio(FILM, "", 2) == 2


def test_audio_aucune_piste() -> None:
    assert tc.choose_audio(FILM[:1], "fre", None) is None


# --- choix des sous-titres -----------------------------------------------------------


def test_audio_dans_ma_langue_seulement_les_forces() -> None:
    assert tc.choose_subtitle(FILM, "fre", "fre", "fre", True, True) == 5


def test_audio_dans_ma_langue_forces_desactives() -> None:
    assert tc.choose_subtitle(FILM, "fre", "fre", "fre", True, False) is None


def test_audio_etranger_sous_titres_complets() -> None:
    # VO anglaise + reglage « Sous-titres si l'audio n'est pas dans ma langue »
    assert tc.choose_subtitle(FILM, "eng", "fre", "fre", True, True) == 6


def test_audio_etranger_sans_le_reglage_forces_de_la_vo() -> None:
    assert tc.choose_subtitle(FILM, "eng", "fre", "fre", False, True) == 7


def test_langue_audio_inconnue_pas_etrangere() -> None:
    assert tc.choose_subtitle(FILM, "", "fre", "fre", True, True) == 5


def test_audio_etranger_seulement_des_forces_dans_ma_langue() -> None:
    pistes = [s for s in FILM if s["Index"] in (0, 1, 5)]
    assert tc.choose_subtitle(pistes, "eng", "fre", "fre", True, True) == 5


# --- libelles des listes (choix manuel) ------------------------------------------------


def test_libelles_audio() -> None:
    assert tc.audio_label(FILM[3], NAMES, WORDS) == "Français (VFF) — EAC3 5.1"
    assert tc.audio_label(FILM[1], NAMES, WORDS) == "Anglais — TRUEHD 7.1 · défaut"
    assert tc.audio_label({"Codec": "aac", "Channels": 2}, NAMES, WORDS) == (
        "Langue inconnue — AAC stéréo"
    )


def test_libelles_sous_titres() -> None:
    assert tc.subtitle_label(FILM[5], NAMES, WORDS) == "Français · forcés"
    assert tc.subtitle_label(FILM[8], NAMES, WORDS) == "Français · externe"
    assert tc.subtitle_label({"Language": "kor"}, NAMES, WORDS) == "KOR"


def test_menu_preselectionne_le_choix_automatique() -> None:
    labels, indexes, pre = tc.menu(FILM, "Audio", NAMES, WORDS, 3)
    assert indexes == [1, 2, 3, 4] and pre == 2
    labels, indexes, pre = tc.menu(FILM, "Subtitle", NAMES, WORDS, None, WORDS["none"])
    assert labels[0] == "Aucun sous-titre" and indexes[0] is None and pre == 0
    assert len(labels) == 5


# --- audio_subs_pref : sans question en automatique --------------------------------------


class FakeDialog:
    def __init__(self, reponses=()) -> None:
        self.reponses = list(reponses)
        self.appels = []

    def select(self, heading, labels, preselect=-1, **_kw):
        self.appels.append((heading, list(labels), preselect))
        return self.reponses.pop(0) if self.reponses else -1


class FakeListItem:
    def __init__(self) -> None:
        self.subs = None

    def setSubtitles(self, subs) -> None:
        self.subs = subs


class FakeDownloadUtils:
    def get_server(self) -> str:
        return "https://emby.example"


SOURCE = {"Id": "src1", "DefaultAudioStreamIndex": 1, "MediaStreams": FILM}
URL = "https://emby.example/emby/videos/42/master.m3u8?MediaSourceId=src1"


def _reglages(monkeypatch, dialog, **valeurs):
    reglages = {
        "transcode_tracks_mode": "0",
        "pref_audio_lang": "fre",
        "pref_subtitle_lang": "fre",
        "subtitle_auto_mode": "1",
        "subtitle_forced_auto": "true",
    }
    reglages.update(valeurs)
    monkeypatch.setattr(
        pu.xbmcaddon,
        "Addon",
        lambda: SimpleNamespace(getSetting=lambda k: reglages.get(k, "")),
        raising=False,
    )
    monkeypatch.setattr(pu.xbmcgui, "Dialog", lambda: dialog, raising=False)
    textes = {30481: "Français", 30482: "Anglais", 30905: "Aucun sous-titre"}
    monkeypatch.setattr(pu, "string_load", lambda i: textes.get(i, "#%s" % i))
    monkeypatch.setattr(pu, "DownloadUtils", FakeDownloadUtils)


def test_automatique_aucune_question(monkeypatch) -> None:
    dialog = FakeDialog()
    _reglages(monkeypatch, dialog)
    url = pu.audio_subs_pref(URL, FakeListItem(), SOURCE, "42", "", "")
    assert dialog.appels == []
    assert url == URL + "&AudioStreamIndex=3&SubtitleStreamIndex=5"


def test_me_demander_listes_preselectionnees(monkeypatch) -> None:
    dialog = FakeDialog(reponses=[0, 2])  # VO anglaise, puis sous-titres complets
    _reglages(monkeypatch, dialog, transcode_tracks_mode="1")
    url = pu.audio_subs_pref(URL, FakeListItem(), SOURCE, "42", "", "")
    (h_audio, l_audio, pre_audio), (h_sub, l_sub, pre_sub) = dialog.appels
    assert h_audio == "#30291" and pre_audio == 2  # VFF deja selectionnee
    assert l_audio[pre_audio] == "Français (VFF) — EAC3 5.1"
    # apres le choix de la VO, la pre-selection suit : sous-titres complets
    assert h_sub == "#30292" and l_sub[pre_sub] == "Français"
    assert url == URL + "&AudioStreamIndex=1&SubtitleStreamIndex=6"


def test_me_demander_retour_garde_le_choix_automatique(monkeypatch) -> None:
    dialog = FakeDialog(reponses=[-1, -1])
    _reglages(monkeypatch, dialog, transcode_tracks_mode="1")
    url = pu.audio_subs_pref(URL, FakeListItem(), SOURCE, "42", "", "")
    assert url == URL + "&AudioStreamIndex=3&SubtitleStreamIndex=5"


def test_tout_lire_jamais_de_question(monkeypatch) -> None:
    dialog = FakeDialog()
    _reglages(monkeypatch, dialog, transcode_tracks_mode="1")
    pu.audio_subs_pref(URL, FakeListItem(), SOURCE, "42", "", "", allow_prompt=False)
    assert dialog.appels == []


def test_choix_explicite_respecte(monkeypatch) -> None:
    dialog = FakeDialog()
    _reglages(monkeypatch, dialog, transcode_tracks_mode="1")
    url = pu.audio_subs_pref(URL, FakeListItem(), SOURCE, "42", "2", "-1")
    assert dialog.appels == []
    assert url == URL + "&AudioStreamIndex=2"


def test_sous_titre_externe_fourni_a_kodi(monkeypatch) -> None:
    dialog = FakeDialog()
    _reglages(monkeypatch, dialog)
    item = FakeListItem()
    url = pu.audio_subs_pref(URL + "|verifypeer=false", item, SOURCE, "42", "", "8")
    assert item.subs == [
        "https://emby.example/emby/Videos/42/src1/Subtitles/8/Stream.srt"
    ]
    assert url == URL + "&AudioStreamIndex=3|verifypeer=false"


def test_sous_titres_kodi_ne_touchent_pas_une_lecture_transcodee(monkeypatch) -> None:
    joueur = SimpleNamespace(appels=[])
    joueur.setSubtitleStream = lambda i: joueur.appels.append(("piste", i))
    joueur.showSubtitles = lambda v: joueur.appels.append(("affiche", v))
    monkeypatch.setattr(pu.xbmc, "Player", lambda: joueur, raising=False)
    monkeypatch.setattr(pu, "_wait_subtitle_streams", lambda: [])
    _reglages(monkeypatch, FakeDialog())
    pu.apply_intelligent_subtitle({"playback_type": "Transcode"})
    assert joueur.appels == []


# --- diagnostic de la qualite automatique ------------------------------------------------


def test_description_de_la_video() -> None:
    source = {"Bitrate": 62400000, "MediaStreams": FILM}
    assert (
        tchk.describe_source(source)
        == "3840x2160 · HEVC HDR10 · 62 400 kb/s · 23.976 i/s"
    )


def test_raisons_du_transcodage() -> None:
    source = {
        "MediaStreams": FILM,
        "TranscodingUrl": "/videos/42/master.m3u8?a=1&TranscodeReasons=ContainerBitrateExceedsLimit,VideoRangeNotSupported",
    }
    assert (
        tchk.transcode_reasons(source)
        == "ContainerBitrateExceedsLimit,VideoRangeNotSupported"
    )
    ligne = tchk.decision_line("Dune", source, "18000", True, "Transcode")
    assert ligne.startswith("Lecture « Dune » : 3840x2160")
    assert "limite 18000 kb/s (qualité auto) -> Transcode" in ligne
    assert ligne.endswith(
        "(raisons Emby : ContainerBitrateExceedsLimit,VideoRangeNotSupported)"
    )
    assert "raisons" not in tchk.decision_line(
        "Dune", source, "90000", False, "DirectStream"
    )


def test_serveur_trop_lent() -> None:
    assert tchk.is_too_slow({"Framerate": 14.2}, 23.976)
    assert not tchk.is_too_slow({"Framerate": 23.0}, 23.976)
    assert not tchk.is_too_slow({"Framerate": 60}, 23.976)
    assert not tchk.is_too_slow({}, 23.976)
    assert not tchk.is_too_slow({"Framerate": 10}, 0)


def test_description_du_transcodage() -> None:
    info = {
        "Width": 1920,
        "Height": 1080,
        "VideoCodec": "h264",
        "Bitrate": 15000000,
        "Framerate": 14.2,
        "VideoDecoderIsHardware": False,
        "VideoEncoderIsHardware": False,
        "TranscodeReasons": ["ContainerBitrateExceedsLimit"],
    }
    assert tchk.describe_transcoding(info) == (
        "1920x1080 · H264 · 15 000 kb/s · 14.2 i/s produites · transcodage logiciel"
        " · raisons : ContainerBitrateExceedsLimit"
    )
    info["VideoDecoderIsHardware"] = True
    assert "décodage matériel" in tchk.describe_transcoding(info)


def test_transcodage_en_pause_ou_video_copiee_jamais_lent() -> None:
    assert not tchk.is_too_slow({"Framerate": 3, "CurrentThrottle": 1}, 23.976)
    assert not tchk.is_too_slow({"Framerate": 3, "IsVideoDirect": True}, 23.976)


def test_transcodage_logiciel_et_cpu() -> None:
    info = {
        "VideoCodec": "h264",
        "VideoDecoderIsHardware": False,
        "VideoEncoderIsHardware": False,
        "CurrentCpuUsage": 97.6,
    }
    assert (
        tchk.describe_transcoding(info)
        == "H264 · transcodage logiciel · CPU serveur 98 %"
    )
    assert "logiciel" not in tchk.describe_transcoding({"VideoCodec": "h264"})


def test_journal_de_decision_titre_avec_accolades(monkeypatch) -> None:
    lignes = []
    journal = SimpleNamespace(
        info=lambda fmt, *a: lignes.append(fmt.format(*a)),
        debug=lambda fmt, *a: lignes.append("DEBUG " + fmt.format(*a)),
    )
    monkeypatch.setattr(pu, "log", journal)
    reglages = {"max_stream_bitrate": "18000", "bitrate_mode": "1"}
    monkeypatch.setattr(
        pu.xbmcaddon,
        "Addon",
        lambda: SimpleNamespace(getSetting=lambda k: reglages.get(k, "")),
        raising=False,
    )
    pu._log_decision("Film {2024}", {"MediaStreams": FILM}, "Transcode", False)
    assert lignes == [
        "Lecture « Film {2024} » : 3840x2160 · HEVC HDR10 · 62 400 kb/s · 23.976 i/s ;"
        " limite 18000 kb/s (qualité auto) -> Transcode"
    ]


# --- verification du transcodage aupres du serveur --------------------------------------


def _serveur(monkeypatch, sessions, joue="42"):
    import json

    import lib.clientinfo as ci
    import lib.downloadutils as du
    import lib.kodi_utils as ku
    import lib.translation as tr

    notifications = []
    urls = []
    monkeypatch.setattr(
        ku, "HomeWindow", lambda: SimpleNamespace(get_property=lambda k: joue)
    )
    monkeypatch.setattr(
        ci, "ClientInformation", lambda: SimpleNamespace(get_device_id=lambda: "dev1")
    )
    monkeypatch.setattr(
        du,
        "DownloadUtils",
        lambda: SimpleNamespace(
            download_url=lambda url, suppress=False: (
                urls.append(url) or json.dumps(sessions)
            )
        ),
    )
    textes = {30899: "Lecture réduite", 30900: "Serveur trop lent : {0} i/s pour {1}"}
    monkeypatch.setattr(tr, "string_load", lambda i: textes[i])
    monkeypatch.setattr(
        pu.xbmcgui,
        "Dialog",
        lambda: SimpleNamespace(notification=lambda *a, **k: notifications.append(a)),
        raising=False,
    )
    return notifications, urls


def test_serveur_trop_lent_notifie(monkeypatch) -> None:
    sessions = [
        {"NowPlayingItem": {"Id": "99"}, "TranscodingInfo": {"Framerate": 60}},
        {"NowPlayingItem": {"Id": "42"}, "TranscodingInfo": {"Framerate": 11.5}},
    ]
    notifications, urls = _serveur(monkeypatch, sessions)
    assert tchk.report_transcoding("42", 23.976, "Dune") is True
    assert urls == ["{server}/emby/Sessions?DeviceId=dev1&format=json"]
    assert notifications == [("Lecture réduite", "Serveur trop lent : 11 i/s pour 24")]


def test_serveur_assez_rapide_silencieux(monkeypatch) -> None:
    sessions = [{"NowPlayingItem": {"Id": "42"}, "TranscodingInfo": {"Framerate": 70}}]
    notifications, _ = _serveur(monkeypatch, sessions)
    assert tchk.report_transcoding("42", 23.976, "Dune") is False
    assert notifications == []


def test_autre_lecture_ou_reponse_vide(monkeypatch) -> None:
    notifications, urls = _serveur(monkeypatch, [], joue="7")
    assert tchk.report_transcoding("42", 23.976, "Dune") is False
    assert urls == []  # la lecture a change : pas de requete
    notifications, _ = _serveur(monkeypatch, {"Error": "x"})
    assert tchk.report_transcoding("42", 23.976, "Dune") is False
    assert notifications == []
