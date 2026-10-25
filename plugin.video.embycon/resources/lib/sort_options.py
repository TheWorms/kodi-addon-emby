# Gnu General Public License - see LICENSE.TXT
"""v1.16 : tris par defaut, par contexte, fixes dans les reglages.

v1.20.0 : un seul reglage par liste, « list_sort-<contexte> », qui reunit le
critere et le sens : "0" = ordre du serveur, sinon <critere><a|d>, par
exemple "9a" = date de sortie croissante, "4d" = date d'ajout decroissante.
Les anciens couples sort-<contexte> / sort_order-<contexte> sont convertis
une fois par settings_migration (voir migrate_sort).

Contextes (media_type de l'URL plugin -> cle des reglages) :
  movies / movie  -> Movies    (mediatheque Films)        tri serveur
  tvshows         -> Series    (mediatheque Series)       tri serveur
  boxsets         -> BoxSets   (liste des collections)    tri serveur + client
  boxset          -> InBoxSet  (contenu d'une collection) tri serveur + client
  series / season -> InSeries  (saisons, episodes)        tri client

Quand un tri est applique (serveur ou client), Kodi recoit « Aucun tri »
comme methode active : il affiche l'ordre recu tel quel au lieu de re-trier
(Kodi trie toujours en croissant, ce qui annulait un tri decroissant serveur
et donnait l'impression que le tri « sautait »).

Module sans dependance Kodi : testable hors Kodi.
"""

from __future__ import annotations

import datetime
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
SORT_SETTING_PREFIX = "list_sort-"
# v1.18.2 : le contenu d'une collection est AUSSI trie cote client : Emby
# renvoie les films d'une collection dans l'ordre d'affichage propre a la
# collection et peut ignorer SortBy (constate : tri par date de sortie sans
# effet dans un widget de collection).
# v1.18.3 : liste des collections aussi (ordre garanti a l'affichage)
CLIENT_CONTEXTS = ("InSeries", "InBoxSet", "BoxSets")

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


def parse_sort(value: str | None) -> tuple[str, bool] | None:
    """'9a' -> ('9', False), '4d' -> ('4', True) ; '0', '' ou inconnu -> None."""
    v = str(value or "").strip()
    if len(v) < 2 or v[-1] not in ("a", "d"):
        return None
    return v[:-1], v[-1] == "d"


def sort_setting(get_setting: GetSetting, context: str | None) -> tuple[str, bool] | None:
    """(critere, decroissant) choisi pour un contexte, None = ordre du serveur."""
    if not context:
        return None
    return parse_sort(get_setting(SORT_SETTING_PREFIX + context))


def is_descending(get_setting: GetSetting, context: str) -> bool:
    spec = sort_setting(get_setting, context)
    return spec is None or spec[1]


def server_sort(get_setting: GetSetting, context: str | None) -> tuple[str, str] | None:
    """(SortBy, SortOrder) Emby pour un contexte trie cote serveur, sinon None."""
    if context not in SERVER_CONTEXTS:
        return None
    spec = sort_setting(get_setting, context)
    sort_by = SORT_FIELD_MAP.get(spec[0]) if spec else None
    if not sort_by:
        return None
    return sort_by, "Descending" if spec[1] else "Ascending"


def client_sort(get_setting: GetSetting, context: str | None) -> tuple[str, bool] | None:
    """(critere, decroissant) pour un contexte trie cote client, sinon None."""
    if context not in CLIENT_CONTEXTS:
        return None
    spec = sort_setting(get_setting, context)
    criterion = _CLIENT_CRITERIA.get(spec[0]) if spec else None
    if criterion is None:
        return None
    if context == "InSeries" and criterion not in (CLIENT_DATE, CLIENT_NAME):
        return None
    return criterion, spec[1]


def migrate_sort(old_field: str | None, old_order: str | None, context: str) -> str:
    """v1.20.0 : ancien couple (sort-X, sort_order-X) -> valeur list_sort-X.

    Les criteres retires sont rapproches du plus proche : Annee -> date de
    sortie, Genre / Nom -> titre ; la note n'existe plus qu'en decroissant.
    """
    field = str(old_field or "0").strip()
    if field in ("", "0"):
        return "0"
    field = {"3": "9", "5": "2", "6": "2"}.get(field, field)
    descending = str(old_order or "0").strip() == "1"
    if context == "InSeries":
        if field == "2":
            return "2a"
        if field != "9":
            return "0"
    if field == "7":
        return "7d"
    if field not in ("2", "4", "9"):
        return "0"
    return field + ("d" if descending else "a")


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


def describe_order(items: list, count: int = 6) -> str:
    """Resume lisible des premiers elements tries (journal de diagnostic)."""
    parts = []
    for item in items[:count]:
        label = ""
        try:
            label = item.list_item.getLabel()
        except Exception:
            label = getattr(item, "sort_name", "")
        parts.append("%s (%s)" % (label, getattr(item, "sort_date", "") or "?"))
    return ", ".join(parts)


def rank_stamps(count: int, now: datetime.datetime | None = None) -> list:
    """v1.19.1 : dates d'ajout decroissantes, une par rang (minute par minute).

    Appliquees apres le tri EmbyCon, elles font qu'un widget de skin trie par
    « date d'ajout, decroissant » (cas d'Arctic) reproduit exactement l'ordre
    choisi dans EmbyCon, croissant ou decroissant.
    """
    base = (now or datetime.datetime.now()).replace(second=0, microsecond=0)
    return [
        (base - datetime.timedelta(minutes=rank)).strftime("%Y-%m-%d %H:%M:%S")
        for rank in range(count)
    ]
