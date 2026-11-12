"""Tests v1.22.5 : bandes-annonces YouTube, reprise demarree au point de reprise."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import xbmc  # noqa: E402

from lib import play_utils  # noqa: E402
from lib.functions import youtube_id_from_url, youtube_trailer_command  # noqa: E402


# --- identifiant YouTube ------------------------------------------------------


def test_identifiant_youtube_toutes_les_formes() -> None:
    vid = "dQw4w9WgXcQ"
    assert youtube_id_from_url("https://www.youtube.com/watch?v=%s" % vid) == vid
    assert youtube_id_from_url("http://www.youtube.com/watch?feature=x&v=%s" % vid) == vid
    assert youtube_id_from_url("https://youtu.be/%s" % vid) == vid
    assert youtube_id_from_url("https://www.youtube.com/embed/%s/" % vid) == vid


def test_identifiant_youtube_refuse_ce_qui_casserait_la_commande() -> None:
    assert youtube_id_from_url(None) is None
    assert youtube_id_from_url("https://www.youtube.com/watch?v=abc),Quit(") is None
    assert youtube_id_from_url("https://example.com/video") is None


def test_bande_annonce_par_wtube_puis_youtube(monkeypatch) -> None:
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    installes = {"plugin.video.wtube"}
    monkeypatch.setattr(xbmc, "getCondVisibility",
                        lambda c: any(a in c for a in installes))
    assert youtube_trailer_command(url) == (
        "PlayMedia(plugin://plugin.video.wtube/?action=play&id=dQw4w9WgXcQ)")
    installes.clear()
    installes.add("plugin.video.youtube")
    assert youtube_trailer_command(url).startswith(
        "RunPlugin(plugin://plugin.video.youtube/play/?video_id=dQw4w9WgXcQ")
    installes.clear()
    assert youtube_trailer_command(url) is None


# --- reprise : demarrage direct au point de reprise ---------------------------


class _Lecteur:
    """Renvoie les positions donnees une a une (la derniere ensuite)."""

    def __init__(self, positions, playing=True) -> None:
        self.positions = list(positions)
        self.playing = playing
        self.sauts = []

    def isPlaying(self) -> bool:
        return self.playing

    def getTime(self) -> float:
        if len(self.positions) > 1:
            return self.positions.pop(0)
        return self.positions[0]

    def seekTime(self, t: float) -> None:
        self.sauts.append(t)


class _Moniteur:
    def waitForAbort(self, s) -> bool:
        return False


def test_point_de_reprise_donne_a_kodi_avant_la_lecture() -> None:
    element = MagicMock()
    play_utils.set_start_offset(element, 996.4)
    element.setProperty.assert_called_once_with("StartOffset", "996.400")
    element = MagicMock()
    play_utils.set_start_offset(element, 0)
    element.setProperty.assert_not_called()


def test_lecture_partie_du_point_de_reprise_aucun_saut(monkeypatch) -> None:
    sauts = []
    monkeypatch.setattr(play_utils, "_seek_and_wait", lambda *a: sauts.append(a) or True)
    lecteur = _Lecteur([0, 0, 0, 986.2])  # ouverture du flux, puis 1re image
    assert play_utils._check_resume_start(lecteur, 996, 20, _Moniteur()) is True
    assert sauts == [] and lecteur.sauts == []


def test_flux_parti_du_debut_saut_de_secours(monkeypatch) -> None:
    sauts = []
    monkeypatch.setattr(play_utils, "_seek_and_wait", lambda *a: sauts.append(a) or True)
    lecteur = _Lecteur([0, 0.4])
    assert play_utils._check_resume_start(lecteur, 996, 20, _Moniteur()) is True
    assert sauts == [(lecteur, 996, 986)]


def test_lecture_arretee_pendant_le_demarrage() -> None:
    lecteur = _Lecteur([0], playing=False)
    assert play_utils._check_resume_start(lecteur, 996, 20, _Moniteur()) is False


def test_aucune_position_la_lecture_est_laissee_telle_quelle(monkeypatch) -> None:
    sauts = []
    monkeypatch.setattr(play_utils, "_seek_and_wait", lambda *a: sauts.append(a) or True)
    lecteur = _Lecteur([0])
    assert play_utils._check_resume_start(lecteur, 996, 1, _Moniteur()) is True
    assert sauts == [] and lecteur.sauts == []
