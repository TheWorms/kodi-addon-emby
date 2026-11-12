# Gnu General Public License - see LICENSE.TXT
"""v1.21.11 : listes EmbyCon gardees en cache par Kodi pendant la navigation.

Constat sur la box (trace des fenetres, 12/11/2026) : quand un film lance
depuis une liste EmbyCon passe en plein ecran, Kodi VIDE la fenetre Videos
(GUIMediaWindow, GUI_MSG_WINDOW_DEINIT -> ClearFileItems). A l'arret du
film, il la rouvre vide et rappelle l'extension, qui reconstruit toute la
liste : on voyait l'explorateur vide, l'indicateur de Kodi puis la boite de
progression pendant 1,5 s ou plus (et Kodi a plante pendant l'un de ces
rechargements).

Les listes sont donc rendues avec cacheToDisc=True : Kodi enregistre une
liste longue a charger (plus d'une seconde) dans special://temp/archive_cache
(fichier « 10025-<crc>.fi » pour la fenetre Videos) et la recharge de la sans
rappeler l'extension au retour d'un film, ou en revenant a une liste parente
avec Retour. Le rafraichissement apres lecture (Container.Refresh) vide ce
cache et recharge la liste en place : l'ancienne reste affichee pendant ce
temps.

Contrepartie : rouvrir depuis l'accueil la categorie qu'on vient de quitter
afficherait la copie en cache, eventuellement perimee. Le service efface
donc les listes EmbyCon de ce cache des qu'on a quitte la fenetre Videos
depuis quelques secondes, sans lecture video en cours (ListingCacheJanitor).
"""
from __future__ import annotations

import os
import time
import urllib.parse

import xbmc
import xbmcvfs

from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)

ADDON_ID = "plugin.video.embycon"
VIDEOS_WINDOW_ID = 10025
CACHE_DIR = "special://temp/archive_cache"
# Delai hors de la fenetre Videos avant d'effacer : au retour d'un film, Kodi
# rouvre la fenetre Videos en moins d'une seconde et doit y trouver la liste.
LEAVE_DELAY = 3.0


def _query(path: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(path).query, keep_blank_values=True)


def is_refresh_in_place(plugin_url: str) -> bool:
    """La fenetre Videos affiche deja cette liste (Container.Refresh) : elle
    reste a l'ecran pendant le rechargement, inutile d'y ajouter la boite de
    progression."""
    if not xbmc.getCondVisibility("Window.IsActive(videos)"):
        return False
    folder = xbmc.getInfoLabel("Container.FolderPath") or ""
    if ADDON_ID not in folder:
        return False
    try:
        shown = int(xbmc.getInfoLabel("Container.NumItems") or 0)
    except ValueError:
        shown = 0
    return shown > 0 and _query(folder) == _query(plugin_url)


def show_progress_for(plugin_url: str) -> bool:
    """Boite de progression seulement quand l'utilisateur ouvre une liste dans
    la fenetre Videos : jamais pour un widget de l'accueil (elle s'affichait
    par-dessus l'accueil), ni pour un rechargement en place."""
    if not xbmc.getCondVisibility("Window.IsActive(videos)"):
        return False
    return not is_refresh_in_place(plugin_url)


def purge(cache_dir: str | None = None) -> int:
    """Efface les listes EmbyCon que Kodi a gardees pour la fenetre Videos.
    Les listes des autres extensions ne sont pas touchees."""
    folder = cache_dir or xbmcvfs.translatePath(CACHE_DIR)
    removed = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    prefix = "%d-" % VIDEOS_WINDOW_ID
    marker = ADDON_ID.encode("ascii")
    for name in names:
        if not (name.startswith(prefix) and name.endswith(".fi")):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            if marker in data:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed


class ListingCacheJanitor:
    """Appele a chaque tour de la boucle du service (environ une seconde)."""

    def __init__(self, delay: float = LEAVE_DELAY, clock=time.time) -> None:
        self.delay = delay
        self.clock = clock
        self.left_at: float | None = None
        self.purged = True  # rien a effacer avant la premiere visite

    def tick(self, in_videos: bool | None = None, playing_video: bool | None = None) -> None:
        try:
            if in_videos is None:
                in_videos = bool(xbmc.getCondVisibility("Window.IsActive(videos)"))
            if playing_video is None:
                playing_video = bool(xbmc.getCondVisibility("Player.HasVideo"))
            if in_videos or playing_video:
                self.left_at = None
                self.purged = False
                return
            if self.purged:
                return
            now = self.clock()
            if self.left_at is None:
                self.left_at = now
                return
            if now - self.left_at >= self.delay:
                self.purged = True
                removed = purge()
                if removed:
                    log.debug("Cache des listes : {0} liste(s) EmbyCon effacee(s)", removed)
        except Exception as error:  # jamais bloquant pour le service
            log.error("Cache des listes : {0}", error)
