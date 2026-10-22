"""Tests v1.15 « Lecture » : film au hasard, Tout lire, marqueurs, debit auto."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

from lib.marker_info import collect_markers  # noqa: E402
from lib.play_utils import build_play_all_url, extract_markers  # noqa: E402
from lib.random_movie import build_random_url, filtre_duree, ligne_infos  # noqa: E402
from lib.server_detect import compute_auto_bitrate  # noqa: E402

MIN = 60 * 10000000  # une minute en ticks


# --- debit auto -----------------------------------------------------------


def test_debit_applique_la_marge_sur_la_mediane() -> None:
    # mediane de 2 mesures = moyenne : (40000 + 60000) / 2 = 50000 -> 80 %
    assert compute_auto_bitrate([40000, 60000], 80, 0, 0) == 40000


def test_debit_ignore_les_mesures_en_echec() -> None:
    assert compute_auto_bitrate([-1, 50000], 80, 0, 0) == 40000
    assert compute_auto_bitrate([-1, -1], 80, 0, 0) == -1


def test_debit_plancher_et_plafond() -> None:
    assert compute_auto_bitrate([1000, 1000], 80, 2000, 0) == 2000
    assert compute_auto_bitrate([200000, 200000], 80, 2000, 120000) == 120000


def test_debit_marge_bornee() -> None:
    # une marge aberrante (0 %) est ramenee a 10 %, jamais un debit nul
    assert compute_auto_bitrate([50000, 50000], 0, 0, 0) == 5000
    assert compute_auto_bitrate([50000, 50000], 150, 0, 0) == 50000


# --- Tout lire ------------------------------------------------------------


def test_collection_triee_par_date_de_sortie_croissante_par_defaut() -> None:
    url = build_play_all_url("abc", "BoxSet", False, "0")
    assert "ParentId=abc" in url
    assert "SortBy=PremiereDate,ProductionYear,SortName" in url
    assert "SortOrder=Ascending" in url
    assert "IncludeItemTypes=Movie,Episode,Video,MusicVideo" in url
    assert "Fields=Chapters," in url


def test_collection_ordre_decroissant_et_nom() -> None:
    assert "SortOrder=Descending" in build_play_all_url("abc", "BoxSet", False, "1")
    assert "SortBy=SortName&SortOrder=Ascending" in build_play_all_url(
        "abc", "BoxSet", False, "2"
    )
    # valeur inconnue -> ordre par defaut
    assert "SortOrder=Ascending" in build_play_all_url("abc", "BoxSet", False, "")


def test_lecture_aleatoire_pour_tous_les_conteneurs() -> None:
    for parent_type in ("BoxSet", "Season", "Playlist"):
        url = build_play_all_url("abc", parent_type, True, "0")
        assert "SortBy=Random" in url
        assert "SortOrder" not in url


def test_saison_garde_l_ordre_serveur() -> None:
    url = build_play_all_url("abc", "Season", False, "0")
    assert "SortBy" not in url
    assert "IncludeItemTypes" not in url


# --- marqueurs ------------------------------------------------------------


CHAPITRES = [
    {"MarkerType": "Chapter", "StartPositionTicks": 0},
    {"MarkerType": "IntroStart", "StartPositionTicks": 30 * 10000000},
    {"MarkerType": "IntroEnd", "StartPositionTicks": 95 * 10000000},
    {"MarkerType": "CreditsStart", "StartPositionTicks": 40 * MIN},
    {"MarkerType": "IntroStart", "StartPositionTicks": 999},
]


def test_extract_markers_premier_de_chaque_type() -> None:
    assert extract_markers(CHAPITRES) == (30 * 10000000, 95 * 10000000, 40 * MIN)


def test_extract_markers_sans_chapitres() -> None:
    assert extract_markers([]) == (0, 0, 0)
    assert extract_markers(None) == (0, 0, 0)


def test_collect_markers_diagnostic() -> None:
    found = collect_markers(CHAPITRES)
    assert found == {
        "IntroStart": 30 * 10000000,
        "IntroEnd": 95 * 10000000,
        "CreditsStart": 40 * MIN,
    }


# --- film au hasard -------------------------------------------------------


def test_url_film_au_hasard() -> None:
    url = build_random_url("lib1", "genre9", True, 1)
    assert "SortBy=Random" in url
    assert "Limit=1" in url
    assert "IsPlayed=False" in url
    assert "ParentId=lib1" in url
    assert "GenreIds=genre9" in url
    assert "IncludeItemTypes=Movie" in url


def test_url_film_au_hasard_vus_compris() -> None:
    url = build_random_url(None, None, False, 1)
    assert "IsPlayed" not in url
    assert "ParentId" not in url
    assert "GenreIds" not in url


def test_filtre_duree() -> None:
    films = [
        {"Id": "court", "RunTimeTicks": 90 * MIN},
        {"Id": "long", "RunTimeTicks": 170 * MIN},
        {"Id": "inconnu", "RunTimeTicks": None},
    ]
    assert [f["Id"] for f in filtre_duree(films, 120)] == ["court", "inconnu"]
    assert len(filtre_duree(films, 0)) == 3


def test_ligne_infos() -> None:
    film = {
        "ProductionYear": 2019,
        "RunTimeTicks": 125 * MIN,
        "Genres": ["Science-fiction", "Drame", "Action", "Thriller"],
        "CommunityRating": 7.84,
    }
    assert ligne_infos(film) == "2019  ·  2h05  ·  Science-fiction, Drame, Action  ·  ★ 7.8"
    assert ligne_infos({"RunTimeTicks": 45 * MIN}) == "45 min"


# --- tirage : exclusion des films deja proposes -----------------------------


def _fake_server(monkeypatch, films, settings=None):
    import lib.random_movie as rm
    from types import SimpleNamespace

    reglages = {"random_movie_unplayed": "true", "random_movie_max_minutes": "0"}
    reglages.update(settings or {})
    urls = []

    def get_content(url):
        urls.append(url)
        return {"Items": list(films)}

    monkeypatch.setattr(rm, "DataManager", lambda: SimpleNamespace(get_content=get_content))
    monkeypatch.setattr(
        rm.xbmcaddon,
        "Addon",
        lambda: SimpleNamespace(getSetting=lambda k: reglages.get(k, "")),
        raising=False,
    )
    return rm, urls


def test_tirage_simple_un_seul_candidat(monkeypatch) -> None:
    rm, urls = _fake_server(monkeypatch, [{"Id": "x"}])
    assert rm.tirer_film()["Id"] == "x"
    assert "Limit=1" in urls[0]


def test_autre_tirage_evite_les_redites(monkeypatch) -> None:
    rm, urls = _fake_server(monkeypatch, [{"Id": "x"}, {"Id": "y"}])
    assert rm.tirer_film(exclus={"x"})["Id"] == "y"
    assert "Limit=30" in urls[0]
    # tout deja propose : on accepte une redite plutot que « aucun film »
    assert rm.tirer_film(exclus={"x", "y"})["Id"] == "x"


def test_tirage_vide(monkeypatch) -> None:
    rm, _ = _fake_server(monkeypatch, [])
    assert rm.tirer_film() is None
