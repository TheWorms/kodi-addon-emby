"""v1.18.4/5 : date de sortie d'une collection = film le plus recent."""

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.collection_dates as cd  # noqa: E402

ENFANTS = {
    "bs-sw": [
        {"PremiereDate": "1977-05-25T00:00:00Z"},
        {"PremiereDate": "2019-12-18T00:00:00Z"},
    ],
    "bs-perso": [{"PremiereDate": "2008-01-01T00:00:00Z"}, {"ProductionYear": 2012}],
    "bs-vide": [],
}


def test_film_le_plus_recent() -> None:
    assert cd.latest_release(ENFANTS["bs-sw"]) == "2019-12-18"
    assert cd.latest_release(ENFANTS["bs-perso"]) == "2012"
    assert cd.latest_release([]) == ""


def test_calcul_en_parallele() -> None:
    actifs, pic = [0], [0]
    verrou = threading.Lock()

    def enfants(bid):
        with verrou:
            actifs[0] += 1
            pic[0] = max(pic[0], actifs[0])
        time.sleep(0.02)
        with verrou:
            actifs[0] -= 1
        return ENFANTS.get(bid, [])

    ids = ["bs-sw", "bs-perso", "bs-vide"] + ["x%d" % i for i in range(13)]
    dates = cd.compute_dates(ids, enfants, workers=8)
    assert dates["bs-sw"] == "2019-12-18" and dates["bs-vide"] == ""
    assert pic[0] > 1  # vraiment en parallele


def test_entrees_manquantes_ou_perimees() -> None:
    now = 1_000_000.0
    entrees = {"a": {"d": "2020", "t": now - 10}, "b": {"d": "", "t": now - 10}, "c": {"d": "2019", "t": 0}}
    assert cd.missing_ids(entrees, ["a", "b", "c", "d"], now) == ["c", "d"]


def test_cache_disque(monkeypatch, tmp_path) -> None:
    chemin = str(tmp_path / "collection_dates.json")
    monkeypatch.setattr(cd, "_file_path", lambda: chemin)
    appels = []

    def enfants(bid):
        appels.append(bid)
        return ENFANTS.get(bid, [])

    dates = cd.collection_release_dates(["bs-sw", "bs-perso", "bs-vide"], enfants)
    assert dates == {"bs-sw": "2019-12-18", "bs-perso": "2012"}
    assert sorted(appels) == ["bs-perso", "bs-sw", "bs-vide"]
    # deuxieme appel : tout vient du disque, aucune requete (meme la vide)
    appels.clear()
    assert cd.collection_release_dates(["bs-sw", "bs-vide"], enfants) == {"bs-sw": "2019-12-18"}
    assert appels == []
    # nouvelle collection : seule elle est lue
    cd.collection_release_dates(["bs-sw", "bs-neuve"], enfants)
    assert appels == ["bs-neuve"]


def _details(identifiant, annee=None, date=None, type_="BoxSet"):
    return SimpleNamespace(id=identifiant, item_type=type_, year=annee, premiere_date=date)


def test_application_aux_elements(monkeypatch) -> None:
    monkeypatch.setattr(
        cd,
        "collection_release_dates",
        lambda ids, fetch_children=None: {"bs-sw": "2019-12-18", "bs-perso": "2012"},
    )
    sw = _details("bs-sw", 1977, "1977-05-25")
    perso = _details("bs-perso", None, "2008-01-01")
    film = _details("m1", 2000, "2000-01-01", type_="Movie")
    cd.apply_collection_dates([sw, perso, film])
    assert (sw.year, sw.premiere_date) == (2019, "2019-12-18")
    assert (perso.year, perso.premiere_date) == (2012, None)
    assert (film.year, film.premiere_date) == (2000, "2000-01-01")


def test_liste_sans_collection_aucune_requete(monkeypatch) -> None:
    def interdit(*_a, **_k):
        raise AssertionError("requete")

    monkeypatch.setattr(cd, "collection_release_dates", interdit)
    cd.apply_collection_dates([_details("m1", type_="Movie")])
