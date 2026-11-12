"""Tests v1.22.4 : reprise d'une lecture reduite sans perdre le point de reprise."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.play_utils as pu  # noqa: E402
import lib.transcode_check as tchk  # noqa: E402


def test_point_de_reprise_garde_tant_que_la_reprise_n_a_pas_eu_lieu() -> None:
    data = {"resume_seconds": 1609}
    # demarrage lent : le lecteur est encore a 0
    assert pu.held_position(data, 0.0) == 1609
    assert pu.held_position(data, 12.0) == 1609
    assert not data.get("resume_reached")
    # la reprise a eu lieu (saut a 1609 - 10 s de recul)
    assert pu.held_position(data, 1599.0) == 1599.0
    assert data["resume_reached"]
    # ensuite, la vraie position, meme si on revient en arriere
    assert pu.held_position(data, 30.0) == 30.0


def test_lecture_depuis_le_debut_non_concernee() -> None:
    assert pu.held_position({"resume_seconds": 0}, 0.0) == 0.0
    assert pu.held_position({}, 42.0) == 42.0
    assert pu.held_position({"resume_seconds": None}, 5.0) == 5.0


def test_verification_du_serveur_seulement_quand_la_video_defile() -> None:
    assert tchk.video_running(True, 3.2, paused=False)
    assert not tchk.video_running(True, 0.0, paused=False)  # demarrage
    assert not tchk.video_running(True, 1599.0, paused=True)  # reprise en pause
    assert not tchk.video_running(False, 10.0, paused=False)


def test_un_seul_saut_puis_attente_en_transcodage(monkeypatch) -> None:
    class Joueur:
        def __init__(self) -> None:
            self.sauts = []
            self.temps = 0.0
            self.appels = 0

        def getPlayingFile(self) -> str:
            return "http://serveur/emby/videos/1/master.m3u8?x=1"

        def isPlaying(self) -> bool:
            return True

        def seekTime(self, t: float) -> None:
            self.sauts.append(t)

        def getTime(self) -> float:
            # le serveur met ~8 s (16 demi-secondes) a rejoindre la position
            self.appels += 1
            return 1600.0 if self.appels > 16 else 0.0

    class Moniteur:
        def abortRequested(self) -> bool:
            return False

    joueur = Joueur()
    monkeypatch.setattr(pu.xbmc, "Monitor", lambda: Moniteur(), raising=False)
    monkeypatch.setattr(pu.xbmc, "sleep", lambda ms: None, raising=False)
    assert pu._seek_and_wait(joueur, 1609, 1599)
    assert joueur.sauts == [1609]  # avant v1.22.4 : 16 demandes de position
