# Gnu General Public License - see LICENSE.TXT
"""v1.15 : « Marqueurs intro / generique » — diagnostic du saut automatique.

Affiche, pour un film ou un episode, les marqueurs que le serveur Emby
renvoie (IntroStart / IntroEnd / CreditsStart), ce qu'EmbyCon en fera avec
les reglages actuels (bouton, saut auto, repli duree fixe) et un rappel de
ce qui releve du serveur. But : savoir en 2 secondes pourquoi un saut ne se
declenche pas.
"""

from __future__ import annotations

from datetime import timedelta

import xbmcaddon
import xbmcgui

from .datamanager import DataManager
from .simple_logging import SimpleLogging
from .translation import string_load

log = SimpleLogging(__name__)

_TICKS_PAR_SECONDE = 10000000

# libelles des modes skip_intros / skip_credits (memes ids que settings.xml)
_MODES_INTRO = {"0": 30442, "1": 30443, "2": 30444}
_MODES_GENERIQUE = {"0": 30442, "1": 30443, "2": 30489}


def _hms(ticks: int) -> str:
    return str(timedelta(seconds=int(ticks / _TICKS_PAR_SECONDE)))


def collect_markers(chapters: list) -> dict[str, int]:
    """Premier marqueur de chaque type, en ticks."""
    found: dict[str, int] = {}
    for chapter in chapters or []:
        marker = chapter.get("MarkerType")
        if marker in ("IntroStart", "IntroEnd", "CreditsStart") and marker not in found:
            found[marker] = chapter.get("StartPositionTicks") or 0
    return found


def _int_setting(settings: xbmcaddon.Addon, key: str) -> int:
    try:
        return int(settings.getSetting(key) or 0)
    except ValueError:
        return 0


def build_report(item: dict, settings: xbmcaddon.Addon) -> str:
    markers = collect_markers(item.get("Chapters") or [])
    aucun = string_load(30543)
    serveur = string_load(30542)

    lignes = []
    titre = item.get("Name") or ""
    if item.get("Type") == "Episode" and item.get("SeriesName"):
        titre = "%s — S%02dE%02d — %s" % (
            item.get("SeriesName"),
            item.get("ParentIndexNumber") or 0,
            item.get("IndexNumber") or 0,
            titre,
        )
    lignes.append(titre)
    lignes.append("")

    fb_intro = _int_setting(settings, "skip_intro_fallback_seconds")
    fb_credits = _int_setting(settings, "skip_credits_fallback_seconds")
    repli = string_load(30544)

    def ligne(libelle_id: int, cle: str, repli_txt: str) -> str:
        if cle in markers:
            valeur = "%s  (%s)" % (_hms(markers[cle]), serveur)
        elif repli_txt:
            valeur = "%s  →  %s" % (aucun, repli_txt)
        else:
            valeur = aucun
        return "%-22s %s" % (string_load(libelle_id) + " :", valeur)

    intro_repli = repli.format(fb_intro) if fb_intro > 0 else ""
    lignes.append(ligne(30539, "IntroStart", intro_repli))
    lignes.append(ligne(30540, "IntroEnd", ""))
    credits_repli = repli.format(fb_credits) if fb_credits > 0 else ""
    lignes.append(ligne(30541, "CreditsStart", credits_repli))
    lignes.append("")

    mode_intro = settings.getSetting("skip_intros") or "0"
    mode_credits = settings.getSetting("skip_credits") or "0"
    lignes.append(
        "%-22s %s" % (string_load(30441) + " :", string_load(_MODES_INTRO.get(mode_intro, 30442)))
    )
    lignes.append(
        "%-22s %s"
        % (string_load(30469) + " :", string_load(_MODES_GENERIQUE.get(mode_credits, 30442)))
    )
    lignes.append("")
    lignes.append(string_load(30545))
    return "\n".join(lignes)


def show_marker_info(item_id: str) -> None:
    url = (
        "{server}/emby/Users/{userid}/Items/%s?fields=Chapters&format=json" % item_id
    )
    item = DataManager().get_content(url)
    if not item:
        log.info("Marqueurs : element {0} introuvable", item_id)
        return
    settings = xbmcaddon.Addon()
    rapport = build_report(item, settings)
    log.info("Marqueurs (diagnostic) {0} : {1}", item_id, collect_markers(item.get("Chapters") or []))
    xbmcgui.Dialog().textviewer(string_load(30532), rapport, usemono=True)
