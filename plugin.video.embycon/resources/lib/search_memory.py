# Gnu General Public License - see LICENSE.TXT
"""v1.22.3 : une liste de resultats de recherche se recharge sans clavier.

Kodi recharge la liste affichee en revenant d'une video (et apres une
action du menu contextuel). L'adresse d'une recherche ne contient pas le
texte cherche : le clavier se rouvrait, et un Retour dessus faisait echouer
le chargement -> Kodi retombait sur l'explorateur. La recherche affichee est
donc memorisee ; tant qu'on est dessus, un rechargement la relance sans
question. Le service l'oublie des qu'on la quitte (accueil, autre liste).

Module sans dependance Kodi : testable hors Kodi.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

PROPERTY = "embycon_search_results"
LEAVE_AFTER = 3  # secondes hors de la liste avant d'oublier la recherche


def _search_params(folder_path: str) -> dict:
    if not folder_path or "plugin.video.embycon" not in folder_path:
        return {}
    query = parse_qs(urlsplit(folder_path).query)
    return {key.lower(): values[0] for key, values in query.items() if values}


def is_search_list(folder_path: str, item_type: str) -> bool:
    """La liste affichee est-elle la recherche (sans texte) de ce type ?"""
    params = _search_params(folder_path)
    return (
        params.get("mode", "").upper() == "NEW_SEARCH"
        and params.get("item_type", "").lower() == (item_type or "").lower()
        and not params.get("query")
    )


def encode(item_type: str, query: str) -> str:
    return json.dumps({"item_type": (item_type or "").lower(), "query": query})


def decode(raw) -> dict | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or not data.get("query"):
        return None
    return data


def query_for_refresh(
    remembered: dict | None, folder_path: str, item_type: str
) -> str | None:
    """Texte a relancer si Kodi recharge la recherche affichee, sinon None."""
    if not remembered or remembered.get("item_type") != (item_type or "").lower():
        return None
    if not is_search_list(folder_path, item_type):
        return None
    return remembered["query"]


def still_on_results(
    remembered: dict | None, folder_path: str, videos_active: bool, playing: bool
) -> bool:
    """Le service doit-il garder la recherche en memoire ?"""
    if not remembered:
        return False
    if playing:
        return True  # lecture lancee depuis les resultats : on y revient
    return videos_active and is_search_list(
        folder_path, remembered.get("item_type", "")
    )
