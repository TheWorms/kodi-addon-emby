"""v1.18.3 : historique des tirages, tri du widget Collections."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

from lib.random_movie import HistoriqueTirages  # noqa: E402
from lib.sort_options import client_sort, server_sort  # noqa: E402


def _tireur(films):
    restants = list(films)

    def tirer():
        return (restants.pop(0), "", "") if restants else None

    return tirer


def _id(entree):
    return entree[0] if entree else None


def test_suivant_precedent_suivant() -> None:
    h = HistoriqueTirages(_tireur(["A", "B", "C"]))
    assert _id(h.suivant()) == "A" and not h.peut_reculer
    assert _id(h.suivant()) == "B" and h.peut_reculer
    # retour au film precedent
    assert _id(h.precedent()) == "A" and not h.peut_reculer
    assert h.precedent() is None and _id(h.courant()) == "A"
    # « Suivant » repasse par B (deja tire) avant d'en tirer un nouveau
    assert _id(h.suivant()) == "B"
    assert _id(h.suivant()) == "C"


def test_plus_de_film() -> None:
    h = HistoriqueTirages(_tireur(["A"]))
    assert _id(h.suivant()) == "A"
    assert h.suivant() is None
    assert _id(h.courant()) == "A"  # on reste sur le dernier film


def test_aucun_film_au_premier_tirage() -> None:
    h = HistoriqueTirages(_tireur([]))
    assert h.suivant() is None and h.courant() is None and not h.peut_reculer


def test_widget_ajouts_recents_n_a_plus_de_tri_propre() -> None:
    """v1.20.0 : le tri des collections est celui de la liste Collections."""
    get = lambda cle: {"list_sort-BoxSets": "9a"}.get(cle, "")  # noqa: E731
    assert server_sort(get, "RecentBoxSets") is None
    assert client_sort(get, "RecentBoxSets") is None


def test_liste_des_collections_triee_cote_client() -> None:
    get = lambda cle: {"list_sort-BoxSets": "9d"}.get(cle, "")  # noqa: E731
    assert client_sort(get, "BoxSets") == ("date", True)
