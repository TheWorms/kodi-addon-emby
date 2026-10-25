"""v1.18.4 : date de sortie d'une collection = film le plus recent."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.collection_dates as cd  # noqa: E402

FILMS = [
    {"Id": "sw4", "PremiereDate": "1977-05-25T00:00:00Z", "ProviderIds": {"TmdbCollection": "10"}},
    {"Id": "sw9", "PremiereDate": "2019-12-18T00:00:00Z", "ProviderIds": {"TmdbCollection": "10"}},
    {"Id": "hp1", "PremiereDate": "2001-11-16T00:00:00Z", "ProviderIds": {"tmdbcollection": "1241"}},
    {"Id": "solo", "PremiereDate": "2015-01-01T00:00:00Z", "ProviderIds": {"Tmdb": "99"}},
]
COLLECTIONS = [
    {"Id": "bs-sw", "ProviderIds": {"Tmdb": "10"}},
    {"Id": "bs-hp", "ProviderIds": {"Tmdb": "1241"}, "PremiereDate": "2001-11-16T00:00:00Z"},
    {"Id": "bs-perso", "ProviderIds": {}},
    {"Id": "bs-vide", "ProviderIds": {}, "ProductionYear": 1990},
]
ENFANTS = {
    "bs-perso": [{"PremiereDate": "2008-01-01T00:00:00Z"}, {"ProductionYear": 2012}],
    "bs-vide": [],
}


def test_date_du_film_le_plus_recent() -> None:
    dates = cd.compute_collection_dates(COLLECTIONS, FILMS, lambda bid: ENFANTS.get(bid, []))
    assert dates["bs-sw"] == "2019-12-18"  # pas 1977 : le film le plus recent
    assert dates["bs-hp"] == "2001-11-16"
    assert dates["bs-perso"] == "2012"  # collection manuelle : lue via son contenu
    assert dates["bs-vide"] == "1990"  # rien d'autre : annee propre de la collection


def test_plafond_de_requetes() -> None:
    appels = []

    def enfants(bid):
        appels.append(bid)
        return []

    perso = [{"Id": "p%d" % i, "ProviderIds": {}} for i in range(10)]
    cd.compute_collection_dates(perso, [], enfants, max_child_queries=3)
    assert len(appels) == 3


def _details(identifiant, annee=None, date=None, type_="BoxSet"):
    return SimpleNamespace(id=identifiant, item_type=type_, year=annee, premiere_date=date)


def test_application_aux_elements(monkeypatch) -> None:
    proprietes = {
        cd._CACHE_PROPERTY: json.dumps(
            {"t": cd.time.time(), "dates": {"bs-sw": "2019-12-18", "bs-perso": "2012"}}
        )
    }
    monkeypatch.setattr(
        cd,
        "HomeWindow",
        lambda: SimpleNamespace(
            get_property=lambda k: proprietes.get(k, ""),
            set_property=lambda k, v: proprietes.__setitem__(k, v),
        ),
    )
    sw = _details("bs-sw", 1977, "1977-05-25")
    perso = _details("bs-perso", None, "2008-01-01")
    film = _details("m1", 2000, "2000-01-01", type_="Movie")
    cd.apply_collection_dates([sw, perso, film])
    assert (sw.year, sw.premiere_date) == (2019, "2019-12-18")
    assert (perso.year, perso.premiere_date) == (2012, None)
    assert (film.year, film.premiere_date) == (2000, "2000-01-01")  # films intacts


def test_cache_relu_sans_requete(monkeypatch) -> None:
    proprietes = {cd._CACHE_PROPERTY: json.dumps({"t": cd.time.time(), "dates": {"x": "2020-01-01"}})}
    monkeypatch.setattr(
        cd, "HomeWindow", lambda: SimpleNamespace(get_property=lambda k: proprietes.get(k, ""))
    )
    monkeypatch.setattr(cd, "_items", lambda _u: (_ for _ in ()).throw(AssertionError("requete")))
    assert cd.collection_release_dates() == {"x": "2020-01-01"}


def test_liste_sans_collection_aucune_requete(monkeypatch) -> None:
    monkeypatch.setattr(cd, "_items", lambda _u: (_ for _ in ()).throw(AssertionError("requete")))
    cd.apply_collection_dates([_details("m1", type_="Movie")])
