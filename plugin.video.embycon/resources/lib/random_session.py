# Gnu General Public License - see LICENSE.TXT
"""v1.21.0 : suite d'un film lance par « Film au hasard ».

- Film arrete en cours de route, ou termine sans lecture continue :
  retour a l'accueil (et non a l'explorateur de l'extension).
- Film termine avec « Enchainer un autre film au hasard » : un nouveau film
  est tire avec les memes criteres (mediatheque, genre, reglages) et lance.

La session vit dans une propriete de la fenetre d'accueil : elle survit aux
invocations du plugin et du service.
"""

from __future__ import annotations

import json

from .kodi_utils import HomeWindow
from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)

PROPERTY = "embycon_random_session"
# meme seuil que l'enchainement des films d'une collection (generique)
FINISHED_PERCENT = 90

IGNORE = "ignore"
NEXT = "next"
HOME = "home"


def decide(session: dict | None, item_id: str, percent: int, continuous: bool) -> str:
    """Que faire a l'arret de item_id ? IGNORE, NEXT ou HOME."""
    if not session or not item_id or session.get("item_id") != item_id:
        return IGNORE
    if continuous and percent >= FINISHED_PERCENT:
        return NEXT
    return HOME


def leave_fullscreen_to_home(
    was_fullscreen: bool, fullscreen: bool, videos_active: bool, random_playing: bool
) -> bool:
    """v1.21.2 : Retour pendant un film au hasard -> accueil.

    Kodi garde la video en fond et reaffiche la fenetre precedente (l'explorateur
    de l'extension). On ne redirige qu'au moment ou l'on quitte le plein ecran :
    naviguer ensuite dans Videos pendant la lecture reste possible.
    """
    return was_fullscreen and not fullscreen and videos_active and random_playing


def start(film_id: str, parent_id: str | None, genre_ids: str | None) -> None:
    session = current() or {}
    same_filters = session.get("parent_id") == parent_id and session.get("genre_ids") == genre_ids
    seen = list(session.get("seen", [])) if same_filters else []
    seen.append(film_id)
    HomeWindow().set_property(
        PROPERTY,
        json.dumps(
            {"item_id": film_id, "parent_id": parent_id, "genre_ids": genre_ids, "seen": seen[-200:]}
        ),
    )


def current() -> dict | None:
    raw = HomeWindow().get_property(PROPERTY)
    if not raw or not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def is_random(item_id: str | None) -> bool:
    session = current()
    return bool(session and item_id and session.get("item_id") == item_id)


def clear() -> None:
    HomeWindow().clear_property(PROPERTY)


def handle_stop(item_id: str, percent: int) -> bool:
    """Appele a l'arret d'une lecture. True si c'etait un film au hasard."""
    import xbmc
    import xbmcaddon
    import xbmcgui

    session = current()
    continuous = xbmcaddon.Addon().getSetting("random_continuous") == "true"
    action = decide(session, item_id, percent, continuous)
    if action == IGNORE:
        return False

    if action == NEXT:
        from .random_movie import tirer_film, lancer_film

        film = tirer_film(session.get("parent_id"), session.get("genre_ids"), set(session.get("seen", [])))
        if film and film.get("Id"):
            log.info("Film au hasard : lecture continue -> {0}", film.get("Name"))
            xbmcgui.Dialog().notification(
                xbmcaddon.Addon().getLocalizedString(30519),
                film.get("Name") or "",
                icon="special://home/addons/plugin.video.embycon/icon.png",
            )
            lancer_film(film.get("Id"), session.get("parent_id"), session.get("genre_ids"))
            return True
        log.info("Film au hasard : plus de film a enchainer")

    log.info("Film au hasard : fin de lecture ({0} %), retour a l'accueil", percent)
    clear()
    xbmc.executebuiltin("ActivateWindow(Home)")
    return True
