# Gnu General Public License - see LICENSE.TXT
"""v1.15 : « Film au hasard » — tire un film et propose de le lancer.

Le widget « Films aleatoires » ne fait qu'afficher une liste. Ici on tire UN
film cote serveur (SortBy=Random), on l'affiche dans un petit dialogue
(affiche, titre, annee, duree, genres, resume) avec trois choix :
Lire / Autre tirage / Annuler. La lecture passe ensuite par le chemin normal
(reprise, sous-titres, saut d'intro conserves).
"""

from __future__ import annotations

from typing import cast

import xbmcaddon
import xbmcgui
import xbmcvfs

from .datamanager import DataManager
from .downloadutils import DownloadUtils
from .simple_logging import SimpleLogging
from .translation import string_load
from .utils import get_emby_url

log = SimpleLogging(__name__)

# Nombre de candidats demandes quand un filtre local (duree) est actif :
# Emby n'expose pas de filtre « duree maximale », on filtre donc cote client.
_CANDIDATS_AVEC_FILTRE = 30

# Choix du dialogue
CHOIX_ANNULER = 0
CHOIX_LIRE = 1
CHOIX_RETIRER = 2


def _lire_reglages() -> tuple[bool, int]:
    settings = xbmcaddon.Addon()
    non_vus = settings.getSetting("random_movie_unplayed") != "false"
    try:
        duree_max = int(settings.getSetting("random_movie_max_minutes") or 0)
    except ValueError:
        duree_max = 0
    return non_vus, max(duree_max, 0)


def build_random_url(
    parent_id: str | None,
    genre_ids: str | None,
    non_vus: bool,
    limite: int,
) -> str:
    params: dict[str, object] = {}
    params["IncludeItemTypes"] = "Movie"
    params["Recursive"] = True
    params["IsMissing"] = False
    params["SortBy"] = "Random"
    params["Limit"] = limite
    params["ImageTypeLimit"] = 1
    params["Fields"] = "Overview,Genres,ProductionYear,RunTimeTicks,CommunityRating"
    params["CollapseBoxSetItems"] = False
    params["GroupItemsIntoCollections"] = False
    if non_vus:
        params["IsPlayed"] = False
    if parent_id:
        params["ParentId"] = parent_id
    if genre_ids:
        params["GenreIds"] = genre_ids
    return get_emby_url("{server}/emby/Users/{userid}/Items", params)


def filtre_duree(items: list, duree_max_minutes: int) -> list:
    """Garde les films dont la duree connue est <= duree_max (0 = sans limite).

    Un film sans duree connue est conserve : mieux vaut le proposer que de
    renvoyer « aucun film » a cause d'une metadonnee manquante.
    """
    if duree_max_minutes <= 0:
        return items
    limite_ticks = duree_max_minutes * 60 * 10000000
    gardes = []
    for item in items:
        ticks = item.get("RunTimeTicks") or 0
        if ticks <= limite_ticks:
            gardes.append(item)
    return gardes


def tirer_film(
    parent_id: str | None = None,
    genre_ids: str | None = None,
    exclus: set | None = None,
) -> dict | None:
    """Tire un film au hasard selon les reglages. None si aucun ne convient."""
    non_vus, duree_max = _lire_reglages()
    limite = _CANDIDATS_AVEC_FILTRE if (duree_max > 0 or exclus) else 1
    url = build_random_url(parent_id, genre_ids, non_vus, limite)
    # DataManager.get_content ne passe PAS par le cache SQLite : chaque appel
    # interroge le serveur, donc chaque tirage est vraiment nouveau.
    result = DataManager().get_content(url)
    if not result:
        return None
    items = result.get("Items") or []
    items = filtre_duree(items, duree_max)
    if exclus:
        restants = [i for i in items if i.get("Id") not in exclus]
        # si tout a deja ete propose, on accepte une redite plutot que rien
        items = restants or items
    if not items:
        return None
    return items[0]


def _format_duree(ticks: int | None) -> str:
    if not ticks:
        return ""
    minutes = int(round(ticks / 10000000.0 / 60.0))
    heures, mins = divmod(minutes, 60)
    if heures:
        return "%dh%02d" % (heures, mins)
    return "%d min" % mins


def ligne_infos(item: dict) -> str:
    morceaux = []
    annee = item.get("ProductionYear")
    if annee:
        morceaux.append(str(annee))
    duree = _format_duree(item.get("RunTimeTicks"))
    if duree:
        morceaux.append(duree)
    genres = item.get("Genres") or []
    if genres:
        morceaux.append(", ".join(genres[:3]))
    note = item.get("CommunityRating")
    if note:
        morceaux.append("★ %.1f" % float(note))
    return "  ·  ".join(morceaux)


class RandomMovieDialog(xbmcgui.WindowXMLDialog):
    """Dialogue Lire / Autre tirage / Annuler (RandomMovieDialog.xml)."""

    choix: int = CHOIX_ANNULER
    film: dict | None = None
    affiche: str = ""

    def __init__(
        self,
        xmlFilename: str,
        scriptPath: str,
        defaultSkin: str = "default",
        defaultRes: str = "720p",
    ) -> None:
        xbmcgui.WindowXMLDialog.__init__(
            self, xmlFilename, scriptPath, defaultSkin, defaultRes
        )
        self.choix = CHOIX_ANNULER

    def onInit(self) -> None:
        film = self.film or {}
        cast(xbmcgui.ControlLabel, self.getControl(4011)).setLabel(
            string_load(30519)
        )
        cast(xbmcgui.ControlLabel, self.getControl(4012)).setLabel(
            film.get("Name") or ""
        )
        cast(xbmcgui.ControlLabel, self.getControl(4013)).setLabel(ligne_infos(film))
        cast(xbmcgui.ControlTextBox, self.getControl(4014)).setText(
            film.get("Overview") or ""
        )
        cast(xbmcgui.ControlImage, self.getControl(4015)).setImage(self.affiche)
        cast(xbmcgui.ControlButton, self.getControl(4020)).setLabel(string_load(30521))
        cast(xbmcgui.ControlButton, self.getControl(4021)).setLabel(string_load(30522))
        cast(xbmcgui.ControlButton, self.getControl(4022)).setLabel(string_load(30523))
        self.setFocusId(4020)

    def onClick(self, controlId: int) -> None:
        if controlId == 4020:
            self.choix = CHOIX_LIRE
        elif controlId == 4021:
            self.choix = CHOIX_RETIRER
        else:
            self.choix = CHOIX_ANNULER
        self.close()

    def onAction(self, action: xbmcgui.Action) -> None:
        if action.getId() in (10, 92):  # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK
            self.choix = CHOIX_ANNULER
            self.close()


def choisir_film_au_hasard(params: dict[str, str]) -> str | None:
    """Boucle de tirage interactive. Renvoie l'Id du film a lire, ou None."""
    parent_id = params.get("parent_id") or None
    if parent_id == "none":
        parent_id = None
    genre_ids = params.get("genre_ids") or None

    settings = xbmcaddon.Addon()
    plugin_path = xbmcvfs.translatePath(settings.getAddonInfo("path"))
    try:
        max_image_width = int(settings.getSetting("max_image_width"))
    except ValueError:
        max_image_width = 0
    download_utils = DownloadUtils()
    server = download_utils.get_server()

    deja_proposes: set = set()
    while True:
        film = tirer_film(parent_id, genre_ids, deja_proposes)
        if film is None:
            log.info("Film au hasard : aucun film ne correspond aux criteres")
            xbmcgui.Dialog().notification(
                string_load(30519),
                string_load(30524),
                icon="special://home/addons/plugin.video.embycon/icon.png",
            )
            return None

        film_id = film.get("Id")
        deja_proposes.add(film_id)
        log.info("Film au hasard : tirage {0} ({1})", film.get("Name"), film_id)

        affiche = ""
        try:
            affiche = download_utils.get_artwork(
                film, "Primary", server=server, maxwidth=max_image_width
            )
        except Exception as err:
            log.debug("Film au hasard : affiche indisponible ({0})", err)

        dialogue = RandomMovieDialog(
            "RandomMovieDialog.xml", plugin_path, "default", "720p"
        )
        dialogue.film = film
        dialogue.affiche = affiche
        dialogue.doModal()
        choix = dialogue.choix
        del dialogue

        if choix == CHOIX_LIRE:
            return film_id
        if choix != CHOIX_RETIRER:
            return None
