"""Tests v1.22.3 : une recherche affichee se recharge sans rouvrir le clavier."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.search_memory as sm  # noqa: E402

RESULTATS = "plugin://plugin.video.embycon/?item_type=Movie&mode=NEW_SEARCH"
MENU = "plugin://plugin.video.embycon/?mode=SEARCH"


def test_recherche_affichee_rechargee_sans_clavier() -> None:
    memoire = sm.decode(sm.encode("movie", "a star is born"))
    assert sm.query_for_refresh(memoire, RESULTATS, "movie") == "a star is born"
    # ordre des parametres indifferent (Kodi les reordonne)
    autre_ordre = "plugin://plugin.video.embycon/?mode=NEW_SEARCH&item_type=Movie"
    assert sm.query_for_refresh(memoire, autre_ordre, "movie") == "a star is born"


def test_nouvelle_recherche_depuis_le_menu_ouvre_le_clavier() -> None:
    memoire = sm.decode(sm.encode("movie", "dune"))
    assert sm.query_for_refresh(memoire, MENU, "movie") is None
    # autre type de recherche, ou rien en memoire
    assert (
        sm.query_for_refresh(memoire, RESULTATS.replace("Movie", "Series"), "series")
        is None
    )
    assert sm.query_for_refresh(None, RESULTATS, "movie") is None
    # une adresse qui porte deja son texte n'est pas concernee
    assert not sm.is_search_list(RESULTATS + "&query=dune", "movie")


def test_memoire_gardee_pendant_la_lecture_et_sur_les_resultats() -> None:
    memoire = sm.decode(sm.encode("movie", "dune"))
    assert sm.still_on_results(memoire, "", videos_active=False, playing=True)
    assert sm.still_on_results(memoire, RESULTATS, videos_active=True, playing=False)


def test_memoire_oubliee_hors_des_resultats() -> None:
    memoire = sm.decode(sm.encode("movie", "dune"))
    assert not sm.still_on_results(memoire, MENU, videos_active=True, playing=False)
    assert not sm.still_on_results(
        memoire, RESULTATS, videos_active=False, playing=False
    )
    assert not sm.still_on_results(None, RESULTATS, videos_active=True, playing=False)


def test_memoire_illisible_ignoree() -> None:
    assert sm.decode("") is None
    assert sm.decode("pas du json") is None
    assert sm.decode('{"item_type": "movie"}') is None
