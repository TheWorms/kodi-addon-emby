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
CLIENT_CONTEXTS = ("InSeries",)

# tri client « dans une serie » : 0 = ordre de la serie, 9 = date, 2/6 = nom
CLIENT_DATE = "date"
CLIENT_NAME = "name"


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
    value = get_setting("sort-" + context)
    if value == "9":
        return CLIENT_DATE, _descending(get_setting, context)
    if value in ("2", "6"):
        return CLIENT_NAME, _descending(get_setting, context)
    return None


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
    return list(items)


def recent_newest_first(get_setting: GetSetting, kind: str) -> bool:
    """Listes « recents » : True = plus recent d'abord (defaut).

    kind : "RecentMovies" ou "RecentSeries". Le serveur renvoie toujours les
    N plus recents ; « plus ancien d'abord » inverse simplement cette liste
    (sinon on obtiendrait les N plus anciens de la mediatheque).
    """
    return get_setting("sort_order-" + kind) != "1"
