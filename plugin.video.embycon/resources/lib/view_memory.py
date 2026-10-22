# Gnu General Public License - see LICENSE.TXT
"""v1.16 : vues memorisees PAR CATEGORIE, appliquees de facon fiable.

Avant : une seule vue par type de contenu Kodi (« movies » servait a la
mediatheque Films, au contenu d'une collection ET aux resultats de recherche),
envoyee juste apres endOfDirectory — souvent avant l'affichage de la liste,
donc ignoree, puis ecrasee par Kodi ou par les « Vues forcees » du skin.

Maintenant :
- une cle par categorie, deduite du chemin du dossier EmbyCon affiche :
  movies@<mediatheque> -> movies, tvshows@<mediatheque> -> tvshows, boxset
  (contenu d'une collection), sets (liste des collections), seasons,
  episodes, genres, alpha, pages, menus ;
- un moniteur (thread du service) qui attend que la liste soit chargee,
  applique la vue, verifie et reessaie pendant ~2 s ;
- la vue choisie par l'utilisateur (via le skin) est memorisee
  automatiquement pour la categorie (reglage), ou via le menu contextuel ;
- stockage dans views.json (profil de l'addon), migration des anciens
  reglages view-<type>.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from .simple_logging import SimpleLogging
from .translation import string_load

log = SimpleLogging(__name__)

PLUGIN_PREFIX = "plugin://plugin.video.embycon"
VIDEO_WINDOW_ID = 10025

# media_type (parametre du chemin plugin) -> categorie de base
_BASE_BY_MEDIA_TYPE = {
    "movies": "movies",
    "movie": "movies",
    "tvshows": "tvshows",
    "boxsets": "sets",
    "boxset": "boxset",
    "series": "seasons",
    "season": "episodes",
    "episodes": "episodes",
    "musicalbums": "albums",
    "musicalbum": "songs",
    "musicartists": "artists",
    "playlists": "playlists",
    "playlist": "playlist",
}

# mode -> categorie, pour les listes sans media_type (menus, genres...)
_BASE_BY_MODE = {
    "GENRES": "genres",
    "MOVIE_ALPHA": "alpha",
    "TVSHOW_ALPHA": "alpha",
    "MOVIE_PAGES": "pages",
    "TVSHOW_PAGES": "pages",
    "SHOW_ADDON_MENU": "menus",
}

# anciens reglages (v1.15 et avant) -> categorie
_LEGACY_SETTINGS = {
    "view-movies": "movies",
    "view-tvshows": "tvshows",
    "view-seasons": "seasons",
    "view-episodes": "episodes",
    "view-sets": "sets",
}

_VIEWS_FILE = "views.json"


def category_chain(folder_path: str) -> list[str]:
    """Cles de vue a consulter pour un dossier, de la plus precise a la plus
    generale. Liste vide si le dossier n'est pas une liste EmbyCon geree.
    """
    if not folder_path or not folder_path.startswith(PLUGIN_PREFIX):
        return []
    query = urllib.parse.urlparse(folder_path).query
    params = urllib.parse.parse_qs(query)
    media_type = (params.get("media_type") or [""])[0].lower().strip()
    mode = (params.get("mode") or [""])[0]

    base = _BASE_BY_MEDIA_TYPE.get(media_type)
    if base is None:
        if not query:
            return ["menus"]  # racine de l'addon
        base = _BASE_BY_MODE.get(mode)
    if base is None:
        return []

    if base in ("movies", "tvshows"):
        inner_url = (params.get("url") or [""])[0]
        inner = urllib.parse.parse_qs(urllib.parse.urlparse(inner_url).query)
        parent = (inner.get("ParentId") or [""])[0]
        if parent and parent != "none":
            return [base + "@" + parent, base]
    return [base]


def is_view_id(control_id: int) -> bool:
    """Convention Kodi : les vues des skins utilisent les ids 50-59 et 500-599."""
    return 50 <= control_id <= 59 or 500 <= control_id <= 599


class ViewStore:
    """views.json : {"version": 1, "views": {categorie: id_de_vue}}.

    Relu a chaque consultation (petit fichier) : le service et le processus
    plugin peuvent l'ecrire tous les deux. Ecriture atomique.
    """

    _lock = threading.Lock()

    def __init__(self, path: str | None = None) -> None:
        if path is None:
            profile = xbmcvfs.translatePath(
                xbmcaddon.Addon().getAddonInfo("profile")
            )
            path = os.path.join(profile, _VIEWS_FILE)
        self.path = path

    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            views = data.get("views", {})
            return views if isinstance(views, dict) else {}
        except FileNotFoundError:
            return self._migrate_legacy()
        except (OSError, ValueError) as err:
            log.error("Vues memorisees illisibles ({0}) : on repart de zero", err)
            return {}

    def _write(self, views: dict) -> None:
        folder = os.path.dirname(self.path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "views": views}, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def _migrate_legacy(self) -> dict:
        """Premiere utilisation : reprend les vues des anciens reglages."""
        views = {}
        try:
            settings = xbmcaddon.Addon()
            for setting_id, category in _LEGACY_SETTINGS.items():
                value = settings.getSetting(setting_id)
                if value and value.isdigit():
                    views[category] = value
                    settings.setSetting(setting_id, "")
        except Exception as err:
            log.error("Migration des vues : {0}", err)
        try:
            self._write(views)
            if views:
                log.info("Vues migrees depuis les anciens reglages : {0}", views)
        except OSError as err:
            log.error("Ecriture des vues impossible : {0}", err)
        return views

    def lookup(self, chain: list[str]) -> str | None:
        with self._lock:
            views = self._read()
        for key in chain:
            value = views.get(key)
            if value:
                return str(value)
        return None

    def save(self, chain: list[str], view_id: int | str) -> None:
        """Memorise pour la categorie la plus precise ; renseigne aussi la
        categorie generale si elle est vide (listes globales sans mediatheque).
        """
        if not chain:
            return
        with self._lock:
            views = self._read()
            views[chain[0]] = str(view_id)
            for key in chain[1:]:
                views.setdefault(key, str(view_id))
            self._write(views)
        log.info("Vue {0} memorisee pour {1}", view_id, chain[0])

    def forget(self, chain: list[str]) -> None:
        if not chain:
            return
        with self._lock:
            views = self._read()
            views.pop(chain[0], None)
            self._write(views)
        log.info("Vue oubliee pour {0}", chain[0])

    def clear(self) -> None:
        with self._lock:
            self._write({})
        log.info("Toutes les vues memorisees ont ete oubliees")


def current_folder_chain() -> list[str]:
    return category_chain(xbmc.getInfoLabel("Container.FolderPath"))


def skin_forced_view_active() -> bool:
    """Arctic Zephyr (et derives) : « Vues forcees » actives pour ce contenu."""
    content = xbmc.getInfoLabel("Container.Content")
    return bool(
        xbmc.getCondVisibility("Skin.HasSetting(enable.forcedviews)")
        and xbmc.getInfoLabel("Skin.String(Skin.ForcedView.%s)" % content)
    )


class ViewMonitor(threading.Thread):
    """Applique la vue memorisee des qu'une liste EmbyCon est affichee."""

    POLL_SECONDS = 0.3
    SETTLE_SECONDS = 2.0
    MAX_ATTEMPTS = 6

    def __init__(self) -> None:
        threading.Thread.__init__(self, daemon=True)
        self.stop_thread = False
        self.store = ViewStore()
        self._warned_skin = False

    def stop_monitor(self) -> None:
        self.stop_thread = True

    def _apply(self, view_id: str) -> None:
        xbmc.executebuiltin("Container.SetViewMode(%s)" % view_id)

    def run(self) -> None:
        log.debug("ViewMonitor demarre")
        monitor = xbmc.Monitor()
        current_path = None
        chain: list[str] = []
        target: str | None = None
        attempts = 0
        settle_until = 0.0
        baseline: int | None = None

        while not monitor.abortRequested() and not self.stop_thread:
            monitor.waitForAbort(self.POLL_SECONDS)
            try:
                if not xbmc.getCondVisibility("Window.IsActive(videos)"):
                    current_path = None
                    continue
                path = xbmc.getInfoLabel("Container.FolderPath")
                if not path.startswith(PLUGIN_PREFIX):
                    current_path = None
                    continue
                if xbmc.getCondVisibility("Container.IsUpdating"):
                    continue

                now = time.time()
                if path != current_path:
                    # nouvelle liste affichee
                    current_path = path
                    chain = category_chain(path)
                    target = self.store.lookup(chain) if chain else None
                    attempts = 0
                    baseline = None
                    settle_until = now + self.SETTLE_SECONDS
                    if target:
                        log.debug("Vue {0} pour {1}", target, chain)
                        self._apply(target)
                        attempts = 1
                    continue

                if now < settle_until:
                    # verification : le skin ou Kodi ont-ils reimpose leur vue ?
                    if (
                        target
                        and attempts < self.MAX_ATTEMPTS
                        and not xbmc.getCondVisibility("Control.IsVisible(%s)" % target)
                    ):
                        attempts += 1
                        self._apply(target)
                        if attempts == self.MAX_ATTEMPTS:
                            self._warn_if_skin_forces(target)
                    continue

                # liste stable : detection d'un changement de vue par l'utilisateur
                focus_id = xbmcgui.Window(VIDEO_WINDOW_ID).getFocusId()
                if not is_view_id(focus_id):
                    continue
                if baseline is None:
                    baseline = focus_id
                    continue
                if focus_id != baseline:
                    baseline = focus_id
                    if xbmcaddon.Addon().getSetting("view_auto_remember") != "false":
                        self.store.save(chain, focus_id)
                        target = str(focus_id)
            except Exception as err:
                log.error("ViewMonitor : {0}", err)

        log.debug("ViewMonitor arrete")

    def _warn_if_skin_forces(self, target: str) -> None:
        log.info("Vue {0} non appliquee apres {1} essais", target, self.MAX_ATTEMPTS)
        if skin_forced_view_active() and not self._warned_skin:
            self._warned_skin = True
            log.info("Les « Vues forcees » du skin ecrasent la vue memorisee")
            xbmcgui.Dialog().notification(
                "EmbyCon",
                string_load(30559),
                icon="special://home/addons/plugin.video.embycon/icon.png",
                time=8000,
            )
