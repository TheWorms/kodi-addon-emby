"""Tests v1.18 : sous-titres forces automatiques."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.play_utils as pu  # noqa: E402

PISTES = [
    {"index": 0, "language": "eng", "isforced": False},
    {"index": 1, "language": "fre", "isforced": False},
    {"index": 2, "language": "eng", "isforced": True},
    {"index": 3, "language": "fre", "isforced": True},
]


# --- choix de la piste forcee --------------------------------------------------


def test_forcee_dans_la_langue_de_l_audio() -> None:
    assert pu.pick_forced_subtitle(PISTES, "French", "fre") == 3
    assert pu.pick_forced_subtitle(PISTES, "eng", "fre") == 2


def test_repli_sur_la_langue_preferee() -> None:
    # audio japonais, pas de forcee japonaise -> forcee francaise
    assert pu.pick_forced_subtitle(PISTES, "jpn", "fre") == 3


def test_jamais_une_forcee_d_une_autre_langue() -> None:
    seulement_anglais = [{"index": 5, "language": "eng", "isforced": True}]
    assert pu.pick_forced_subtitle(seulement_anglais, "fre", "fre") is None


def test_aucune_piste_forcee() -> None:
    assert pu.pick_forced_subtitle(PISTES[:2], "fre", "fre") is None
    assert pu.pick_forced_subtitle([], "fre", "fre") is None


# --- application selon les reglages ------------------------------------------------


class FakePlayer:
    def __init__(self) -> None:
        self.stream = None
        self.shown = None

    def setSubtitleStream(self, idx) -> None:
        self.stream = idx

    def showSubtitles(self, visible) -> None:
        self.shown = visible


def _lecture(monkeypatch, reglages, audio="fre", sous_titres_affiches=False, pistes=PISTES):
    player = FakePlayer()
    monkeypatch.setattr(
        pu.xbmcaddon,
        "Addon",
        lambda: SimpleNamespace(getSetting=lambda k: reglages.get(k, "")),
        raising=False,
    )
    monkeypatch.setattr(pu.xbmc, "Player", lambda: player, raising=False)
    monkeypatch.setattr(pu.xbmc, "getInfoLabel", lambda _l: audio, raising=False)
    monkeypatch.setattr(
        pu.xbmc,
        "getCondVisibility",
        lambda c: sous_titres_affiches if c == "VideoPlayer.SubtitlesEnabled" else False,
        raising=False,
    )
    monkeypatch.setattr(pu, "_kodi_subtitle_streams", lambda: list(pistes))
    monkeypatch.setattr(pu.xbmc, "sleep", lambda _ms: None, raising=False)
    return player


def test_mode_desactive_forcees_auto_activees(monkeypatch) -> None:
    reglages = {"subtitle_auto_mode": "0", "subtitle_forced_auto": "true", "pref_subtitle_lang": "fre"}
    player = _lecture(monkeypatch, reglages, audio="fre")
    pu.apply_intelligent_subtitle({})
    assert (player.stream, player.shown) == (3, True)


def test_reglage_par_defaut_actif(monkeypatch) -> None:
    # reglage jamais touche (chaine vide) = active
    player = _lecture(monkeypatch, {"subtitle_auto_mode": "0"}, audio="fre")
    pu.apply_intelligent_subtitle({})
    assert player.stream == 3


def test_sous_titres_deja_affiches_respectes(monkeypatch) -> None:
    reglages = {"subtitle_auto_mode": "0", "subtitle_forced_auto": "true"}
    player = _lecture(monkeypatch, reglages, sous_titres_affiches=True)
    pu.apply_intelligent_subtitle({})
    assert player.stream is None


def test_choix_manuel_respecte(monkeypatch) -> None:
    reglages = {"subtitle_auto_mode": "0", "subtitle_forced_auto": "true"}
    player = _lecture(monkeypatch, reglages)
    pu.apply_intelligent_subtitle({"subtitle_stream_index": "4"})
    assert player.stream is None


def test_forcees_auto_desactivees(monkeypatch) -> None:
    reglages = {"subtitle_auto_mode": "0", "subtitle_forced_auto": "false"}
    player = _lecture(monkeypatch, reglages)
    pu.apply_intelligent_subtitle({})
    assert player.stream is None


def test_mode_intelligent_audio_preferee_forcee(monkeypatch) -> None:
    reglages = {
        "subtitle_auto_mode": "1",
        "subtitle_forced_auto": "true",
        "pref_audio_lang": "fre",
        "pref_subtitle_lang": "fre",
    }
    player = _lecture(monkeypatch, reglages, audio="fre")
    pu.apply_intelligent_subtitle({})
    assert (player.stream, player.shown) == (3, True)


def test_mode_intelligent_sans_forcees_auto_masque(monkeypatch) -> None:
    reglages = {
        "subtitle_auto_mode": "1",
        "subtitle_forced_auto": "false",
        "pref_audio_lang": "fre",
        "pref_subtitle_lang": "fre",
    }
    player = _lecture(monkeypatch, reglages, audio="fre")
    pu.apply_intelligent_subtitle({})
    assert (player.stream, player.shown) == (None, False)


def test_mode_intelligent_audio_etrangere_sous_titres_complets(monkeypatch) -> None:
    reglages = {
        "subtitle_auto_mode": "1",
        "subtitle_forced_auto": "true",
        "pref_audio_lang": "fre",
        "pref_subtitle_lang": "fre",
    }
    player = _lecture(monkeypatch, reglages, audio="eng")
    pu.apply_intelligent_subtitle({})
    assert (player.stream, player.shown) == (1, True)
