"""Tests v1.21.0 : suite d'un film au hasard (accueil ou lecture continue)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.play_utils as pu  # noqa: E402
import lib.random_session as rs  # noqa: E402

SESSION = {"item_id": "m1", "parent_id": None, "genre_ids": None, "seen": ["m1"]}


def test_decision() -> None:
    assert rs.decide(SESSION, "m1", 40, continuous=True) == rs.HOME  # arret en cours
    assert rs.decide(SESSION, "m1", 97, continuous=False) == rs.HOME  # fini, sans suite
    assert rs.decide(SESSION, "m1", 97, continuous=True) == rs.NEXT  # fini, suite
    assert rs.decide(SESSION, "autre", 97, continuous=True) == rs.IGNORE
    assert rs.decide(None, "m1", 97, continuous=True) == rs.IGNORE


def _arret(monkeypatch, position, continu, tirage=("m2", "Dune")):
    lances, accueil, notifs = [], [], []
    monkeypatch.setattr(rs, "current", lambda: dict(SESSION))
    monkeypatch.setattr(rs, "clear", lambda: None)
    monkeypatch.setattr(
        sys.modules["xbmcaddon"],
        "Addon",
        lambda: SimpleNamespace(
            getSetting=lambda k: {
                "random_continuous": "true" if continu else "false",
                "promptDeleteEpisodePercentage": "100",
                "promptDeleteMoviePercentage": "100",
                "next_movie_mode": "2",
            }.get(k, ""),
            getLocalizedString=lambda i: "Film au hasard",
        ),
        raising=False,
    )
    monkeypatch.setattr(sys.modules["xbmc"], "executebuiltin", accueil.append, raising=False)
    monkeypatch.setattr(sys.modules["xbmcgui"], "Dialog", lambda: SimpleNamespace(notification=lambda *a, **k: notifs.append(a)), raising=False)
    import lib.random_movie as rm

    monkeypatch.setattr(rm, "tirer_film", lambda *a: {"Id": tirage[0], "Name": tirage[1]} if tirage else None)
    monkeypatch.setattr(rm, "lancer_film", lambda fid, *a: lances.append(fid))
    envois = []
    monkeypatch.setattr(pu, "send_event_notification", lambda m, d: envois.append(d))
    data = {
        "item_type": "Movie",
        "next_episode": {"Id": "suite-collection", "Name": "X"},
        "currentPossition": position,
        "duration": 100,
        "can_delete": False,
    }
    pu.prompt_for_stop_actions("m1", data)
    return lances, accueil, envois


def test_arret_en_cours_retour_accueil(monkeypatch) -> None:
    lances, accueil, envois = _arret(monkeypatch, 40, continu=True)
    assert accueil == ["ActivateWindow(Home)"] and lances == [] and envois == []


def test_fin_sans_suite_retour_accueil(monkeypatch) -> None:
    lances, accueil, envois = _arret(monkeypatch, 97, continu=False)
    # pas de film suivant de collection non plus
    assert accueil == ["ActivateWindow(Home)"] and lances == [] and envois == []


def test_fin_lecture_continue(monkeypatch) -> None:
    lances, accueil, envois = _arret(monkeypatch, 97, continu=True)
    assert lances == ["m2"] and accueil == [] and envois == []


def test_plus_de_film_retour_accueil(monkeypatch) -> None:
    lances, accueil, _ = _arret(monkeypatch, 97, continu=True, tirage=None)
    assert lances == [] and accueil == ["ActivateWindow(Home)"]
