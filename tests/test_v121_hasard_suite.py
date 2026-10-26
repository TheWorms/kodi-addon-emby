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


# --- bouton « Passer » qui disparait ----------------------------------------


def test_bouton_passer_disparait() -> None:
    from lib.skip_intro_dialog import button_expired

    assert not button_expired(None, 100.0, 10)  # pas encore affiche
    assert not button_expired(100.0, 105.0, 10)
    assert button_expired(100.0, 110.0, 10)
    assert not button_expired(100.0, 500.0, 0)  # 0 = jusqu'a la fin


def test_retour_depuis_le_plein_ecran() -> None:
    assert rs.leave_fullscreen_to_home(True, False, True, True)
    assert not rs.leave_fullscreen_to_home(False, False, True, True)  # deja hors plein ecran
    assert not rs.leave_fullscreen_to_home(True, False, False, True)  # pas l'explorateur
    assert not rs.leave_fullscreen_to_home(True, False, True, False)  # pas un film au hasard
    assert not rs.leave_fullscreen_to_home(True, True, True, True)


def test_fin_naturelle_compte_comme_vu_jusqu_au_bout(monkeypatch) -> None:
    """v1.21.3 : journal de Thib, fin de lecture vue a 84 % (position datee)."""
    lances = []
    monkeypatch.setattr(rs, "current", lambda: dict(SESSION))
    monkeypatch.setattr(rs, "clear", lambda: None)
    monkeypatch.setattr(
        sys.modules["xbmcaddon"],
        "Addon",
        lambda: SimpleNamespace(
            getSetting=lambda k: {"random_continuous": "true", "promptDeleteEpisodePercentage": "100",
                                  "promptDeleteMoviePercentage": "100"}.get(k, ""),
            getLocalizedString=lambda i: "Film au hasard",
        ),
        raising=False,
    )
    monkeypatch.setattr(sys.modules["xbmcgui"], "Dialog", lambda: SimpleNamespace(notification=lambda *a, **k: None), raising=False)
    import lib.random_movie as rm

    monkeypatch.setattr(rm, "tirer_film", lambda *a: {"Id": "m2", "Name": "Dune"})
    monkeypatch.setattr(rm, "lancer_film", lambda fid, *a: lances.append(fid))
    data = {"item_type": "Movie", "next_episode": None, "currentPossition": 84, "duration": 100,
            "can_delete": False, "playback_ended": True}
    pu.prompt_for_stop_actions("m1", data)
    assert lances == ["m2"]


def test_bouton_se_ferme_seul(monkeypatch) -> None:
    from lib import skip_intro_dialog as sid

    fermes = []
    monkeypatch.setattr(sid.SkipIntroDialog, "close", lambda self: fermes.append(1), raising=False)
    d = sid.SkipIntroDialog.__new__(sid.SkipIntroDialog)
    d.dialog_open = True
    d.timeout = 10
    d.expire()
    assert fermes == [1] and not d.dialog_open
    d.expire()  # deja ferme : rien
    d.dismiss()
    assert fermes == [1]
