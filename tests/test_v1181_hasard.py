"""v1.18.1 : le « Film au hasard » se lance quelle que soit la facon d'ouvrir l'entree."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.random_movie as rm  # noqa: E402


def _env(monkeypatch, fenetre_videos: bool, film="m1"):
    appels = {"fin_dossier": [], "lance": [], "tirage": 0}

    def tirage(_params):
        appels["tirage"] += 1
        return film

    monkeypatch.setattr(rm, "choisir_film_au_hasard", tirage)
    monkeypatch.setattr(rm, "_lancer", lambda fid: appels["lance"].append(fid))
    monkeypatch.setattr(
        rm.xbmcplugin,
        "endOfDirectory",
        lambda h, **kw: appels["fin_dossier"].append((h, kw.get("succeeded"))),
        raising=False,
    )
    monkeypatch.setattr(
        rm.xbmc,
        "getCondVisibility",
        lambda c: fenetre_videos if c == "Window.IsActive(videos)" else False,
        raising=False,
    )
    return appels


def test_runplugin_lance_directement(monkeypatch) -> None:
    appels = _env(monkeypatch, fenetre_videos=False)
    rm.lancer_film_au_hasard({}, -1)
    assert appels["lance"] == ["m1"] and appels["fin_dossier"] == []


def test_ouvert_comme_dossier_depuis_un_menu(monkeypatch) -> None:
    appels = _env(monkeypatch, fenetre_videos=True)
    rm.lancer_film_au_hasard({}, 7)
    # Kodi recoit « echec » (pas de liste affichee) puis le film est lance
    assert appels["fin_dossier"] == [(7, False)]
    assert appels["lance"] == ["m1"]


def test_charge_comme_widget_ne_lance_rien(monkeypatch) -> None:
    appels = _env(monkeypatch, fenetre_videos=False)
    rm.lancer_film_au_hasard({}, 7)
    assert appels["fin_dossier"] == [(7, False)]
    assert appels["tirage"] == 0 and appels["lance"] == []


def test_annule_ne_lance_rien(monkeypatch) -> None:
    appels = _env(monkeypatch, fenetre_videos=True, film=None)
    rm.lancer_film_au_hasard({}, 7)
    assert appels["lance"] == []


def test_reglage_lanceur(monkeypatch) -> None:
    monkeypatch.setattr(
        rm.xbmcaddon, "Addon", lambda: SimpleNamespace(getSetting=lambda _k: ""), raising=False
    )
    assert rm.random_widget_launches() is True
    monkeypatch.setattr(
        rm.xbmcaddon, "Addon", lambda: SimpleNamespace(getSetting=lambda _k: "false"), raising=False
    )
    assert rm.random_widget_launches() is False
