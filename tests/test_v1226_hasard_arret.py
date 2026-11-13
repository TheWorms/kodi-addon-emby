"""Tests v1.22.6 : le film en cours est arrete avant le tirage au hasard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.random_movie as rm  # noqa: E402
import lib.random_session as rs  # noqa: E402


class Joueur:
    def __init__(self, video: bool = True) -> None:
        self.video = video
        self.arrets = 0

    def isPlayingVideo(self) -> bool:
        return self.video

    def isPlaying(self) -> bool:
        return self.video

    def stop(self) -> None:
        self.arrets += 1
        self.video = False


class Fenetre:
    def __init__(self) -> None:
        self.props = {}

    def set_property(self, key, value) -> None:
        self.props[key] = value

    def get_property(self, key) -> str:
        return self.props.get(key, "")

    def clear_property(self, key) -> None:
        self.props.pop(key, None)


def test_film_en_cours_arrete_sans_enchainement(monkeypatch) -> None:
    fenetre = Fenetre()
    fenetre.set_property(rs.PROPERTY, '{"film": "151821"}')
    monkeypatch.setattr(rs, "HomeWindow", lambda: fenetre)
    joueur = Joueur()
    assert rm._stop_video_behind(joueur) is True
    assert joueur.arrets == 1
    # la session « au hasard » du film arrete est fermee : rien ne s'enchaine
    assert fenetre.get_property(rs.PROPERTY) == ""
    assert fenetre.get_property(rs.STOP_PROPERTY) != ""


def test_aucune_video_rien_n_est_arrete(monkeypatch) -> None:
    fenetre = Fenetre()
    monkeypatch.setattr(rs, "HomeWindow", lambda: fenetre)
    joueur = Joueur(video=False)
    assert rm._stop_video_behind(joueur) is False
    assert joueur.arrets == 0 and fenetre.props == {}


def test_marqueur_d_arret_recent_seulement() -> None:
    assert rs.stop_was_for_random("1000.0", 1005.0)
    assert not rs.stop_was_for_random("1000.0", 1030.0)  # trop ancien
    assert not rs.stop_was_for_random("", 1000.0)
    assert not rs.stop_was_for_random("abc", 1000.0)


def test_marqueur_consomme_une_seule_fois(monkeypatch) -> None:
    fenetre = Fenetre()
    monkeypatch.setattr(rs, "HomeWindow", lambda: fenetre)
    rs.mark_stop_for_random(2000.0)
    assert rs.consume_stop_for_random(2003.0) is True
    assert rs.consume_stop_for_random(2004.0) is False


def test_tirage_arrete_d_abord_le_film(monkeypatch) -> None:
    etapes = []
    monkeypatch.setattr(
        rm, "_stop_video_behind", lambda: etapes.append("arret") or True
    )
    monkeypatch.setattr(
        rm, "choisir_film_au_hasard", lambda params: etapes.append("fiche") or "83871"
    )
    monkeypatch.setattr(
        rm, "lancer_film", lambda film_id, parent, genres: etapes.append(film_id)
    )
    rm.lancer_film_au_hasard({}, handle=-1)
    assert etapes == ["arret", "fiche", "83871"]
