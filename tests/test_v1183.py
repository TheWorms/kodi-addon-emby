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


def _reglages(**valeurs):
    base = {"sort-RecentBoxSets": "4", "sort_order-RecentBoxSets": "1"}
    base.update({k.replace("__", "-"): v for k, v in valeurs.items()})
    return lambda cle: base.get(cle, "")


def test_widget_collections_par_defaut_date_d_ajout() -> None:
    assert server_sort(_reglages(), "RecentBoxSets") == ("DateCreated,SortName", "Descending")
    assert client_sort(_reglages(), "RecentBoxSets") == ("added", True)


def test_widget_collections_date_de_sortie_decroissante() -> None:
    get = _reglages(**{"sort__RecentBoxSets": "9"})
    assert server_sort(get, "RecentBoxSets") == (
        "PremiereDate,ProductionYear,SortName",
        "Descending",
    )
    assert client_sort(get, "RecentBoxSets") == ("date", True)
    get = _reglages(**{"sort__RecentBoxSets": "9", "sort_order__RecentBoxSets": "0"})
    assert client_sort(get, "RecentBoxSets") == ("date", False)


def test_liste_des_collections_triee_cote_client() -> None:
    get = lambda cle: {"sort-BoxSets": "9", "sort_order-BoxSets": "1"}.get(cle, "")  # noqa: E731
    assert client_sort(get, "BoxSets") == ("date", True)
