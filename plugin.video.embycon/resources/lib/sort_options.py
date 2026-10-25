# Gnu General Public License - see LICENSE.TXT
"""v1.16 : tris par defaut, par contexte, fixes dans les reglages.

Contextes (media_type de l'URL plugin -> cle des reglages) :
  movies / movie  -> Movies    (mediatheque Films)        tri serveur
  tvshows         -> Series    (mediatheque Series)       tri serveur
  boxsets         -> BoxSets   (liste des collections)    tri serveur
  boxset          -> InBoxSet  (contenu d'une collection) tri serveur
  series / season -> InSeries  (saisons, episodes)        tri client

Quand un tri est applique (serveur ou client), Kodi recoit « Aucun tri »
comme methode active : il affiche l'ordre recu tel quel au lieu de re-trier
(Kodi trie toujours en croissant, ce qui annulait un tri decroissant serveur
et donnait l'impression que le tri « sautait »).

Module sans dependance Kodi : testable hors Kodi.
"""

from __future__ import annotations

from typing import Callable

GetSetting = Callable[[str], str]

# valeur du reglage sort-<contexte> -> champ(s) Emby SortBy
SORT_FIELD_MAP = {
    "2": "SortName",  # Titre
    "3": "ProductionYear,SortName",  # Annee
    "4": "DateCreated,SortName",  # Date d'ajout
    "5": "Genres",  # Genre
    "6": "SortName",  # Nom
    "7": "CommunityRating,SortName",  # Note
    "9": "PremiereDate,ProductionYear,SortName",  # Date de sortie
}

SERVER_CONTEXTS = ("Movies", "Series", "BoxSets", "InBoxSet")
# v1.18.2 : le contenu d'une collection est AUSSI trie cote client : Emby
# renvoie les films d'une collection dans l'ordre d'affichage propre a la
# collection et peut ignorer SortBy (constate : tri par date de sortie sans
# effet dans un widget de collection).
CLIENT_CONTEXTS = ("InSeries", "InBoxSet")

# criteres de tri client
CLIENT_DATE = "date"
CLIENT_NAME = "name"
CLIENT_ADDED = "added"
CLIENT_RATING = "rating"

# valeur du reglage sort-<contexte> -> critere client
_CLIENT_CRITERIA = {
    "9": CLIENT_DATE,  # Date de sortie
    "3": CLIENT_DATE,  # Annee (la date complete departage)
    "2": CLIENT_NAME,  # Titre
    "6": CLIENT_NAME,  # Nom
    "4": CLIENT_ADDED,  # Date d'ajout
    "7": CLIENT_RATING,  # Note
}


def sort_context(media_type: str | None) -> str | None:
    mt = str(media_type or "").lower().strip()
    if mt in ("movies", "movie"):
        return "Movies"
    if mt == "tvshows":
        return "Series"
    if mt == "boxsets":
        return "BoxSets"
    if mt == "boxset":
        return "InBoxSet"
    if mt in ("series", "season"):
        return "InSeries"
    return None


def _descending(get_setting: GetSetting, context: str) -> bool:
    return get_setting("sort_order-" + context) == "1"


def server_sort(get_setting: GetSetting, context: str | None) -> tuple[str, str] | None:
    """(SortBy, SortOrder) Emby pour un contexte trie cote serveur, sinon None."""
    if context not in SERVER_CONTEXTS:
        return None
    sort_by = SORT_FIELD_MAP.get(get_setting("sort-" + context))
    if not sort_by:
        return None
    order = "Descending" if _descending(get_setting, context) else "Ascending"
    return sort_by, order


def client_sort(get_setting: GetSetting, context: str | None) -> tuple[str, bool] | None:
    """(critere, decroissant) pour un contexte trie cote client, sinon None."""
    if context not in CLIENT_CONTEXTS:
        return None
    criterion = _CLIENT_CRITERIA.get(get_setting("sort-" + context))
    if criterion is None:
        return None
    if context == "InSeries" and criterion not in (CLIENT_DATE, CLIENT_NAME):
        return None
    return criterion, _descending(get_setting, context)


def sort_gui_items(items: list, criterion: str, descending: bool) -> list:
    """Trie des GuiItem (attributs sort_date / sort_name / sort_index).

    Les elements sans cle (pseudo-element « Tous les episodes », page
    suivante...) restent a la fin, dans leur ordre d'origine.
    """
    if criterion == CLIENT_DATE:
        sortable = [i for i in items if getattr(i, "sort_date", "")]
        rest = [i for i in items if not getattr(i, "sort_date", "")]
        # a date egale (ou annee seule), l'ordre de la serie departage
        sortable.sort(
            key=lambda i: (i.sort_date, getattr(i, "sort_index", (0, 0))),
            reverse=descending,
        )
        return sortable + rest
    if criterion == CLIENT_NAME:
        sortable = [i for i in items if getattr(i, "sort_name", "")]
        rest = [i for i in items if not getattr(i, "sort_name", "")]
        sortable.sort(key=lambda i: i.sort_name.lower(), reverse=descending)
        return sortable + rest
    if criterion == CLIENT_ADDED:
        sortable = [i for i in items if getattr(i, "sort_added", "")]
        rest = [i for i in items if not getattr(i, "sort_added", "")]
        sortable.sort(key=lambda i: i.sort_added, reverse=descending)
        return sortable + rest
    if criterion == CLIENT_RATING:
        return sorted(
            items, key=lambda i: getattr(i, "sort_rating", 0.0) or 0.0, reverse=descending
        )
    return list(items)


def _release_date(item: dict) -> str:
    premiere = str(item.get("PremiereDate") or "")[:10]
    year = item.get("ProductionYear") or 0
    if not premiere and year:
        premiere = str(year)
    return premiere


def _name_key(item: dict) -> str:
    return str(item.get("SortName") or item.get("Name") or "").lower()


def sort_emby_items(items: list, collection_order: str) -> list:
    """v1.18.2 : trie des elements Emby bruts (dicts) d'une collection.

    collection_order (reglage collection_play_order) : 0 = date de sortie
    croissante, 1 = decroissante, 2 = nom. Sert a « Tout lire » et au « film
    suivant », independamment de l'ordre renvoye par le serveur.
    """
    if collection_order == "2":
        return sorted(items, key=_name_key)
    dated = [i for i in items if _release_date(i)]
    undated = [i for i in items if not _release_date(i)]
    dated.sort(key=lambda i: (_release_date(i), _name_key(i)), reverse=collection_order == "1")
    # sans date connue : toujours a la fin, par nom
    return dated + sorted(undated, key=_name_key)


def recent_newest_first(get_setting: GetSetting, kind: str) -> bool:
    """Listes « recents » : True = plus recent d'abord (defaut).

    kind : "RecentMovies" ou "RecentSeries". Le serveur renvoie toujours les
    N plus recents ; « plus ancien d'abord » inverse simplement cette liste
    (sinon on obtiendrait les N plus anciens de la mediatheque).
    """
    return get_setting("sort_order-" + kind) != "1"
