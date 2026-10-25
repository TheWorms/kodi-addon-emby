# Gnu General Public License - see LICENSE.TXT
"""v1.15 : « Film au hasard » — tire un film et propose de le lancer.

Le widget « Films aleatoires » ne fait qu'afficher une liste. Ici on tire UN
film cote serveur (SortBy=Random), on l'affiche dans un petit dialogue
(affiche, titre, annee, duree, genres, resume) avec trois choix :
Lire / Autre tirage / Annuler. La lecture passe ensuite par le chemin normal
(reprise, sous-titres, saut d'intro conserves).
"""

from __future__ import annotations

from typing import Callable, cast

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from .datamanager import DataManager
from .downloadutils import DownloadUtils
from .simple_logging import SimpleLogging
from .translation import string_load
from .utils import get_emby_url, send_event_notification

log = SimpleLogging(__name__)

# Nombre de candidats demandes quand un filtre local (duree) est actif :
# Emby n'expose pas de filtre « duree maximale », on filtre donc cote client.
_CANDIDATS_AVEC_FILTRE = 30

# Largeur demandee pour le fanart plein ecran du dialogue
FANART_WIDTH = 1920

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


class HistoriqueTirages:
    """v1.18.3 : historique des tirages pour « Precedent » / « Suivant ».

    Chaque entree est un tuple (film, affiche, fond). « Suivant » avance dans
    l'historique s'il y a des tirages deja vus devant, sinon tire un nouveau
    film ; « Precedent » revient au tirage d'avant. Classe sans Kodi : testable.
    """

    def __init__(self, tirer: Callable[[], tuple | None]) -> None:
        self._tirer = tirer
        self._entrees: list = []
        self._index = -1

    def courant(self) -> tuple | None:
        if 0 <= self._index < len(self._entrees):
            return self._entrees[self._index]
        return None

    @property
    def peut_reculer(self) -> bool:
        return self._index > 0

    def suivant(self) -> tuple | None:
        """Entree suivante (deja vue ou nouveau tirage) ; None si aucun film."""
        if self._index + 1 < len(self._entrees):
            self._index += 1
            return self.courant()
        entree = self._tirer()
        if entree is None:
            return None
        self._entrees.append(entree)
        self._index = len(self._entrees) - 1
        return entree

    def precedent(self) -> tuple | None:
        if not self.peut_reculer:
            return None
        self._index -= 1
        return self.courant()


class RandomMovieDialog(xbmcgui.WindowXMLDialog):
    """Dialogue « Film au hasard » (RandomMovieDialog.xml).

    v1.18.2 : plein ecran avec le fanart du film en fond.
    v1.18.3 : s'ouvre IMMEDIATEMENT (fond noir + « Tirage en cours ») puis
    tire le film : on ne voit plus l'explorateur de l'extension pendant la
    requete. Boutons « Precedent » / « Lire » / « Suivant » / « Annuler » ;
    touches piste precedente / suivante de la telecommande aussi.
    """

    choix: int = CHOIX_ANNULER
    historique: HistoriqueTirages | None = None

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

    @property
    def film(self) -> dict | None:
        entree = self.historique.courant() if self.historique else None
        return entree[0] if entree else None

    def onInit(self) -> None:
        cast(xbmcgui.ControlLabel, self.getControl(4011)).setLabel(
            string_load(30519)
        )
        cast(xbmcgui.ControlButton, self.getControl(4023)).setLabel(string_load(30577))
        cast(xbmcgui.ControlButton, self.getControl(4020)).setLabel(string_load(30521))
        cast(xbmcgui.ControlButton, self.getControl(4021)).setLabel(string_load(30522))
        cast(xbmcgui.ControlButton, self.getControl(4022)).setLabel(string_load(30523))
        self.setFocusId(4020)
        if self.historique is not None and self.historique.courant() is None:
            self._chargement()
            if self.historique.suivant() is None:
                self._aucun_film()
                self.close()
                return
        self._afficher()

    def _chargement(self) -> None:
        cast(xbmcgui.ControlLabel, self.getControl(4012)).setLabel(string_load(30578))
        cast(xbmcgui.ControlLabel, self.getControl(4013)).setLabel("")
        cast(xbmcgui.ControlTextBox, self.getControl(4014)).setText("")

    def _aucun_film(self) -> None:
        xbmcgui.Dialog().notification(
            string_load(30519),
            string_load(30524),
            icon="special://home/addons/plugin.video.embycon/icon.png",
        )

    def _afficher(self) -> None:
        entree = self.historique.courant() if self.historique else None
        if entree is None:
            return
        film, affiche, fond = entree
        cast(xbmcgui.ControlLabel, self.getControl(4012)).setLabel(
            film.get("Name") or ""
        )
        cast(xbmcgui.ControlLabel, self.getControl(4013)).setLabel(ligne_infos(film))
        cast(xbmcgui.ControlTextBox, self.getControl(4014)).setText(
            film.get("Overview") or ""
        )
        cast(xbmcgui.ControlImage, self.getControl(4015)).setImage(affiche)
        cast(xbmcgui.ControlImage, self.getControl(4016)).setImage(fond)
        cast(xbmcgui.ControlButton, self.getControl(4023)).setEnabled(
            bool(self.historique and self.historique.peut_reculer)
        )

    def _suivant(self) -> None:
        if self.historique is None:
            return
        self._chargement()
        if self.historique.suivant() is None:
            self._aucun_film()
        self._afficher()

    def _precedent(self) -> None:
        if self.historique is not None and self.historique.precedent() is not None:
            self._afficher()

    def onClick(self, controlId: int) -> None:
        if controlId == 4021:
            self._suivant()
            return
        if controlId == 4023:
            self._precedent()
            if not (self.historique and self.historique.peut_reculer):
                self.setFocusId(4020)
            return
        self.choix = CHOIX_LIRE if controlId == 4020 else CHOIX_ANNULER
        self.close()

    def onAction(self, action: xbmcgui.Action) -> None:
        action_id = action.getId()
        if action_id in (10, 92):  # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK
            self.choix = CHOIX_ANNULER
            self.close()
        elif action_id == 14:  # ACTION_NEXT_ITEM (piste suivante)
            self._suivant()
        elif action_id == 15:  # ACTION_PREV_ITEM (piste precedente)
            self._precedent()


def _image(download_utils: DownloadUtils, film: dict, kind: str, server, width: int) -> str:
    try:
        return download_utils.get_artwork(film, kind, server=server, maxwidth=width) or ""
    except Exception as err:
        log.debug("Film au hasard : image {0} indisponible ({1})", kind, err)
        return ""


def choisir_film_au_hasard(params: dict[str, str]) -> str | None:
    """Tirage interactif. Renvoie l'Id du film a lire, ou None."""
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

    def prochain() -> tuple | None:
        film = tirer_film(parent_id, genre_ids, deja_proposes)
        if film is None:
            log.info("Film au hasard : aucun film ne correspond aux criteres")
            return None
        deja_proposes.add(film.get("Id"))
        log.info("Film au hasard : tirage {0} ({1})", film.get("Name"), film.get("Id"))
        affiche = _image(download_utils, film, "Primary", server, max_image_width)
        fond = _image(download_utils, film, "Backdrop", server, FANART_WIDTH)
        return film, affiche, fond

    # le dialogue s'ouvre tout de suite ; le premier tirage se fait dedans
    dialogue = RandomMovieDialog("RandomMovieDialog.xml", plugin_path, "default", "720p")
    dialogue.historique = HistoriqueTirages(prochain)
    dialogue.doModal()
    choix = dialogue.choix
    film = dialogue.film or {}
    del dialogue

    if choix == CHOIX_LIRE and film.get("Id"):
        return film.get("Id")
    return None


def _lancer(film_id: str) -> None:
    """Meme chemin que functions.play_action (sans import circulaire)."""
    xbmc.Player().stop()
    send_event_notification(
        "embycon_play_action",
        {
            "action": "play",
            "item_id": film_id,
            "auto_resume": "-1",
            "force_transcode": False,
            "media_source_id": "",
        },
    )


def lancer_film_au_hasard(params: dict[str, str], handle: int = -1) -> None:
    """v1.18.1 : point d'entree unique du « Film au hasard ».

    Kodi peut appeler le chemin de trois facons :
    - RunPlugin(...) (menu contextuel, raccourci Arctic « action ») :
      handle = -1, on tire et on lance ;
    - ActivateWindow(Videos, ...) / clic dans une liste (raccourci Arctic
      vers le chemin) : handle >= 0, Kodi attend un dossier -> on lui repond
      « echec » pour qu'il ne reste pas bloque ni n'affiche de liste, puis on
      tire et on lance ;
    - chargement d'un widget (accueil, hub du skin) : handle >= 0 hors de
      la fenetre Videos -> on ne lance RIEN (sinon le dialogue surgirait a
      chaque affichage).
    """
    if handle >= 0:
        try:
            xbmcplugin.endOfDirectory(
                handle, succeeded=False, updateListing=False, cacheToDisc=False
            )
        except Exception as err:
            log.debug("Film au hasard : endOfDirectory ({0})", err)
        if not xbmc.getCondVisibility("Window.IsActive(videos)"):
            log.info("Film au hasard : charge comme widget, rien a lancer")
            return
    film_id = choisir_film_au_hasard(params)
    if film_id:
        _lancer(film_id)
        return
    # v1.18.3 : Annuler (ou Retour) ramene a l'accueil au lieu de laisser
    # l'explorateur de l'extension affiche derriere le dialogue
    if xbmc.getCondVisibility("Window.IsActive(videos)"):
        log.info("Film au hasard : annule, retour a l'accueil")
        xbmc.executebuiltin("ActivateWindow(Home)")


def random_widget_launches() -> bool:
    """Reglage : « Films - Aleatoire » ouvert en plein ecran lance un film."""
    return xbmcaddon.Addon().getSetting("random_widget_launches") != "false"
