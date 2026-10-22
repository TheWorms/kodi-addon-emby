"""v1.15 : « Tout lire » prepare au fil de l'eau (simulation sans Kodi)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.play_utils as pu  # noqa: E402


class FakePlaylist:
    def __init__(self) -> None:
        self.urls: list = []

    def clear(self) -> None:
        self.urls = []

    def add(self, url, _li=None) -> None:
        self.urls.append(url)


class FakePlayer:
    """Lecteur simule : demarre sur play(), peut etre arrete a la volee."""

    def __init__(self, stop_after_adds: int = -1) -> None:
        self.playing = False
        self.current = None
        self.play_calls = 0
        self.stop_after_adds = stop_after_adds

    def play(self, playlist) -> None:
        self.play_calls += 1
        self.playing = True
        self.current = playlist.urls[0]

    def isPlaying(self) -> bool:
        return self.playing

    def getPlayingFile(self) -> str:
        return self.current or ""


def _setup(monkeypatch, items_ok, player, playlist):
    def fake_prepare(item, *_args):
        if item["Id"] not in items_ok:
            return None
        url = "http://srv/" + item["Id"]
        # simulation : l'utilisateur arrete la lecture apres N ajouts
        if player.stop_after_adds == len(playlist.urls):
            player.playing = False
        return url, object()

    monkeypatch.setattr(pu, "_prepare_play_all_item", fake_prepare)
    monkeypatch.setattr(pu.xbmc, "PlayList", lambda _kind: playlist, raising=False)
    monkeypatch.setattr(pu.xbmc, "Player", lambda: player, raising=False)
    monkeypatch.setattr(pu.xbmc, "sleep", lambda _ms: None, raising=False)
    monkeypatch.setattr(pu.xbmc, "getInfoLabel", lambda _l: "", raising=False)
    monkeypatch.setattr(
        pu.xbmc,
        "Monitor",
        lambda: SimpleNamespace(abortRequested=lambda: False),
        raising=False,
    )
    monkeypatch.setattr(
        pu, "DownloadUtils", lambda: SimpleNamespace(get_server=lambda: "http://srv")
    )
    addon = SimpleNamespace(getSetting=lambda _k: "400")
    monkeypatch.setattr(pu.xbmcaddon, "Addon", lambda: addon, raising=False)


def test_demarre_au_premier_element_et_ajoute_la_suite(monkeypatch) -> None:
    playlist, player = FakePlaylist(), FakePlayer()
    _setup(monkeypatch, {"a", "b", "c"}, player, playlist)
    items = [{"Id": "a"}, {"Id": "b"}, {"Id": "c"}]
    assert pu.play_all_files(items, "-1", SimpleNamespace()) is None
    assert player.play_calls == 1
    assert playlist.urls == ["http://srv/a", "http://srv/b", "http://srv/c"]


def test_element_illisible_saute(monkeypatch) -> None:
    playlist, player = FakePlaylist(), FakePlayer()
    _setup(monkeypatch, {"b", "c"}, player, playlist)
    items = [{"Id": "a"}, {"Id": "b"}, {"Id": "c"}]
    pu.play_all_files(items, "-1", SimpleNamespace())
    assert player.play_calls == 1
    assert playlist.urls == ["http://srv/b", "http://srv/c"]


def test_arret_utilisateur_interrompt_la_preparation(monkeypatch) -> None:
    playlist, player = FakePlaylist(), FakePlayer(stop_after_adds=2)
    _setup(monkeypatch, {"a", "b", "c", "d"}, player, playlist)
    items = [{"Id": "a"}, {"Id": "b"}, {"Id": "c"}, {"Id": "d"}]
    pu.play_all_files(items, "-1", SimpleNamespace())
    # arret pendant la preparation du 3e : on n'ajoute plus rien ensuite
    assert playlist.urls == ["http://srv/a", "http://srv/b", "http://srv/c"]


def test_intros_tout_ou_rien(monkeypatch) -> None:
    playlist, player = FakePlaylist(), FakePlayer()
    _setup(monkeypatch, {"a"}, player, playlist)
    items = [{"Id": "a"}, {"Id": "b"}]
    assert pu.play_all_files(items, "-1", SimpleNamespace(), play_items=False) is None
    assert player.play_calls == 0


def test_aucun_element_lisible(monkeypatch) -> None:
    playlist, player = FakePlaylist(), FakePlayer()
    _setup(monkeypatch, set(), player, playlist)
    assert pu.play_all_files([{"Id": "a"}], "-1", SimpleNamespace()) is None
    assert player.play_calls == 0
