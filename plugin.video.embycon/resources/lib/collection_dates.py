# Gnu General Public License - see LICENSE.TXT
"""v1.18.4 : date de sortie d'une collection = celle de son film le plus recent.

Probleme : Emby ne renseigne souvent ni annee ni date de sortie sur une
collection (BoxSet). Le tri « date de sortie » d'EmbyCon et le tri « Annee »
d'un widget Arctic n'avaient donc rien sur quoi trier : l'ordre restait
alphabetique ou aleatoire.

Solution : on calcule pour chaque collection la date de sortie de son film le
plus recent, en 2 requetes au lieu d'une par collection :
  1. toutes les collections (ProviderIds -> id de collection TMDb) ;
  2. tous les films (ProviderIds.TmdbCollection + PremiereDate).
Les collections sans id TMDb (creees a la main) sont completees en lisant
leur contenu (nombre de requetes plafonne). Resultat garde 1 h dans une
propriete de la fenetre d'accueil (partagee entre les appels du plugin).
"""

from __future__ import annotations

import json
import time
from typing import Callable

from .datamanager import DataManager
from .kodi_utils import HomeWindow
from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)

_CACHE_PROPERTY = "embycon_collection_dates"
_CACHE_TTL = 3600
_MIN_REFRESH_AGE = 60  # une collection inconnue relance le calcul apres 60 s
_MAX_CHILD_QUERIES = 40


def release_date(item: dict) -> str:
    """'AAAA-MM-JJ', ou 'AAAA' si seule l'annee est connue, sinon ''."""
    premiere = str(item.get("PremiereDate") or "")[:10]
    if len(premiere) == 10:
        return premiere
    year = item.get("ProductionYear")
    return str(year) if year else ""


def provider_id(item: dict, provider: str) -> str | None:
    for key, value in (item.get("ProviderIds") or {}).items():
        if str(key).lower() == provider.lower() and value:
            return str(value)
    return None


def compute_collection_dates(
    boxsets: list,
    movies: list,
    fetch_children: Callable[[str], list],
    max_child_queries: int = _MAX_CHILD_QUERIES,
) -> dict:
    """{id_collection: date du film le plus recent}. Fonction pure (testable)."""
    latest_by_tmdb: dict = {}
    for movie in movies:
        collection = provider_id(movie, "TmdbCollection")
        date = release_date(movie)
        if collection and date and date > latest_by_tmdb.get(collection, ""):
            latest_by_tmdb[collection] = date

    dates: dict = {}
    queries = 0
    for boxset in boxsets:
        boxset_id = boxset.get("Id")
        if not boxset_id:
            continue
        tmdb = provider_id(boxset, "Tmdb")
        date = latest_by_tmdb.get(tmdb, "") if tmdb else ""
        if not date and queries < max_child_queries:
            queries += 1
            children = [release_date(c) for c in fetch_children(boxset_id) or []]
            children = [d for d in children if d]
            date = max(children) if children else ""
        if not date:
            date = release_date(boxset)
        if date:
            dates[boxset_id] = date
    return dates


def _items(url: str) -> list:
    result = DataManager().get_content(url)
    return list((result or {}).get("Items") or [])


def _fetch_children(boxset_id: str) -> list:
    return _items(
        "{server}/emby/Users/{userid}/Items?ParentId=" + boxset_id
        + "&Fields=PremiereDate,ProductionYear&EnableImages=false"
        "&EnableUserData=false&format=json"
    )


def _read_cache() -> tuple[float, dict]:
    raw = HomeWindow().get_property(_CACHE_PROPERTY)
    if not raw:
        return 0.0, {}
    try:
        data = json.loads(raw)
        return float(data.get("t", 0)), dict(data.get("dates") or {})
    except (ValueError, TypeError):
        return 0.0, {}


def collection_release_dates(force: bool = False) -> dict:
    """Dates des collections (cache 1 h)."""
    stamp, dates = _read_cache()
    if not force and dates and time.time() - stamp < _CACHE_TTL:
        return dates
    start = time.time()
    boxsets = _items(
        "{server}/emby/Users/{userid}/Items?IncludeItemTypes=BoxSet&Recursive=true"
        "&Fields=ProviderIds,PremiereDate,ProductionYear&EnableImages=false"
        "&EnableUserData=false&format=json"
    )
    movies = _items(
        "{server}/emby/Users/{userid}/Items?IncludeItemTypes=Movie&Recursive=true"
        "&Fields=ProviderIds,PremiereDate,ProductionYear&EnableImages=false"
        "&EnableUserData=false&format=json"
    )
    dates = compute_collection_dates(boxsets, movies, _fetch_children)
    HomeWindow().set_property(
        _CACHE_PROPERTY, json.dumps({"t": time.time(), "dates": dates})
    )
    log.info(
        "Collections : date de sortie calculee pour {0}/{1} collections en {2:.1f} s",
        len(dates),
        len(boxsets),
        time.time() - start,
    )
    return dates


def apply_collection_dates(item_list: list) -> None:
    """Renseigne annee + date de sortie des collections d'une liste d'ItemDetails.

    Donne a Kodi (tri « Annee » d'un widget Arctic) et au tri EmbyCon une
    vraie date : celle du film le plus recent de chaque collection.
    """
    boxsets = [d for d in item_list if getattr(d, "item_type", None) == "BoxSet"]
    if not boxsets:
        return
    try:
        dates = collection_release_dates()
        if any(d.id not in dates for d in boxsets):
            stamp, _ = _read_cache()
            if time.time() - stamp > _MIN_REFRESH_AGE:
                dates = collection_release_dates(force=True)
    except Exception as err:
        log.error("Collections : calcul des dates impossible ({0})", err)
        return
    for details in boxsets:
        date = dates.get(details.id)
        if not date:
            continue
        details.year = int(date[:4])
        # annee seule : on retire la date Emby (premier film) pour rester coherent
        details.premiere_date = date if len(date) == 10 else None
