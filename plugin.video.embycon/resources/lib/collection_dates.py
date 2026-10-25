# Gnu General Public License - see LICENSE.TXT
"""Date de sortie d'une collection = celle de son film le plus recent.

v1.18.4 : Emby ne renseigne ni annee ni date de sortie sur les collections
(BoxSet) : les tris « date de sortie » d'EmbyCon et « Annee » d'un widget
Arctic n'avaient rien sur quoi trier.

v1.18.5 : constate sur le serveur (240 collections) : le raccourci TMDb ne
marche pas (aucun film n'expose l'id de sa collection) et seules 40
collections etaient datees, en 11 s. Desormais :
- le contenu de chaque collection est lu EN PARALLELE (8 requetes a la fois) ;
- le resultat est garde SUR DISQUE (collection_dates.json, profil de
  l'addon), valable 3 jours par collection : il survit aux redemarrages ;
- le service le prepare en arriere-plan (au demarrage puis toutes les 12 h),
  donc un widget n'attend normalement jamais ;
- une collection inconnue (nouvelle) est datee a la volee.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import xbmcaddon
import xbmcvfs

from .datamanager import DataManager
from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)

_FILE_NAME = "collection_dates.json"
ENTRY_MAX_AGE = 3 * 24 * 3600
_WORKERS = 8
_lock = threading.Lock()


def release_date(item: dict) -> str:
    """'AAAA-MM-JJ', ou 'AAAA' si seule l'annee est connue, sinon ''."""
    premiere = str(item.get("PremiereDate") or "")[:10]
    if len(premiere) == 10:
        return premiere
    year = item.get("ProductionYear")
    return str(year) if year else ""


def latest_release(children: list) -> str:
    dates = [release_date(c) for c in children or []]
    dates = [d for d in dates if d]
    return max(dates) if dates else ""


def missing_ids(entries: dict, ids: list, now: float, max_age: float = ENTRY_MAX_AGE) -> list:
    """Collections sans date en cache, ou dont la date est trop ancienne."""
    out = []
    for boxset_id in ids:
        entry = entries.get(boxset_id)
        if not entry or now - float(entry.get("t", 0)) > max_age:
            out.append(boxset_id)
    return out


def compute_dates(ids: list, fetch_children: Callable[[str], list], workers: int = _WORKERS) -> dict:
    """{id: date du film le plus recent ('' si inconnue)}, requetes en parallele."""
    if not ids:
        return {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(ids)))) as pool:
        results = list(pool.map(lambda bid: latest_release(fetch_children(bid)), ids))
    return dict(zip(ids, results))


# --------------------------------------------------------------- stockage ---


def _file_path() -> str:
    profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
    return os.path.join(profile, _FILE_NAME)


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", {})
        return entries if isinstance(entries, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: str, entries: dict) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"v": 2, "entries": entries}, f)
    os.replace(tmp, path)


# ---------------------------------------------------------------- serveur ---


def _items(url: str) -> list:
    result = DataManager().get_content(url)
    return list((result or {}).get("Items") or [])


def _fetch_children(boxset_id: str) -> list:
    return _items(
        "{server}/emby/Users/{userid}/Items?ParentId=" + boxset_id
        + "&Fields=PremiereDate,ProductionYear&EnableImages=false"
        "&EnableUserData=false&format=json"
    )


def _all_boxset_ids() -> list:
    boxsets = _items(
        "{server}/emby/Users/{userid}/Items?IncludeItemTypes=BoxSet&Recursive=true"
        "&EnableImages=false&EnableUserData=false&format=json"
    )
    return [b.get("Id") for b in boxsets if b.get("Id")]


def collection_release_dates(
    ids: list,
    fetch_children: Callable[[str], list] | None = None,
    allow_stale: bool = True,
) -> dict:
    """Dates (film le plus recent) des collections `ids`, depuis le cache disque.

    v1.18.6 : par defaut (widgets, listes), une date perimee est utilisee telle
    quelle — seul le service la rafraichit (allow_stale=False) : un widget ne
    bloque plus 20 s quand le cache expire. Seules les collections jamais
    datees sont lues a la volee.
    """
    fetch = fetch_children or _fetch_children
    path = _file_path()
    with _lock:
        entries = _load(path)
        now = time.time()
        if allow_stale:
            todo = [i for i in ids if i not in entries]
        else:
            todo = missing_ids(entries, ids, now)
        if todo:
            start = time.time()
            for boxset_id, date in compute_dates(todo, fetch).items():
                entries[boxset_id] = {"d": date, "t": now}
            try:
                _save(path, entries)
            except OSError as err:
                log.error("Collections : cache des dates non enregistre ({0})", err)
            log.info(
                "Collections : {0} collection(s) datee(s) en {1:.1f} s ({2} deja en cache)",
                len(todo),
                time.time() - start,
                len(ids) - len(todo),
            )
    return {i: entries[i]["d"] for i in ids if i in entries and entries[i].get("d")}


def refresh_all_collection_dates() -> None:
    """Service : prepare le cache pour toutes les collections du serveur."""
    try:
        ids = _all_boxset_ids()
        if ids:
            dates = collection_release_dates(ids, allow_stale=False)
            log.info("Collections : {0}/{1} collections ont une date de sortie", len(dates), len(ids))
    except Exception as err:
        log.error("Collections : preparation des dates impossible ({0})", err)


def apply_collection_dates(item_list: list, release_as_date_added: bool = False) -> None:
    """Renseigne annee + date de sortie des collections d'une liste d'ItemDetails.

    Donne a Kodi (tri « Annee » d'un widget Arctic) et au tri EmbyCon une
    vraie date : celle du film le plus recent de chaque collection.

    v1.18.6 : release_as_date_added (tri EmbyCon des collections regle sur
    « Date de sortie ») -> la date d'ajout transmise a Kodi devient aussi la
    date de sortie. Un widget Arctic trie par « date d'ajout » (son reglage
    par defaut, il n'a pas de tri « date de sortie ») suit alors la date de
    sortie, sans rien changer dans le skin.
    """
    boxsets = [d for d in item_list if getattr(d, "item_type", None) == "BoxSet"]
    if not boxsets:
        return
    try:
        dates = collection_release_dates([d.id for d in boxsets])
    except Exception as err:
        log.error("Collections : calcul des dates impossible ({0})", err)
        return
    for details in boxsets:
        date = dates.get(details.id)
        if not date:
            continue
        details.year = int(date[:4])
        # annee seule : on retire la date Emby pour rester coherent
        details.premiere_date = date if len(date) == 10 else None
        if release_as_date_added:
            full = date if len(date) == 10 else date + "-01-01"
            details.date_added = full + " 00:00:00"
