"""v1.21.11 : cache des listes EmbyCon dans la fenetre Videos."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import xbmc  # noqa: E402

from lib import listing_cache  # noqa: E402
from lib.listing_cache import ListingCacheJanitor, purge  # noqa: E402


def _ecrire(dossier, nom, contenu):
    (dossier / nom).write_bytes(contenu)


def test_purge_ne_touche_que_les_listes_embycon_de_videos(tmp_path) -> None:
    _ecrire(tmp_path, "10025-aaaa0001.fi", b"..plugin://plugin.video.embycon/?mode=GET_CONTENT..")
    _ecrire(tmp_path, "10025-aaaa0002.fi", b"..plugin://plugin.video.catchuptvandmore/..")
    _ecrire(tmp_path, "10502-aaaa0003.fi", b"..plugin.video.embycon..")
    _ecrire(tmp_path, "aaaa0004.fi", b"..plugin.video.embycon..")
    assert purge(str(tmp_path)) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "10025-aaaa0002.fi", "10502-aaaa0003.fi", "aaaa0004.fi"]


def test_purge_dossier_absent(tmp_path) -> None:
    assert purge(str(tmp_path / "absent")) == 0


class _Horloge:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_retour_de_film_garde_le_cache(monkeypatch) -> None:
    appels = []
    monkeypatch.setattr(listing_cache, "purge", lambda *a: appels.append(1) or 1)
    h = _Horloge()
    j = ListingCacheJanitor(delay=3.0, clock=h)
    j.tick(in_videos=True, playing_video=False)      # liste ouverte
    j.tick(in_videos=False, playing_video=True)      # film en plein ecran
    h.t = 100
    j.tick(in_videos=False, playing_video=False)     # arret : transition
    h.t = 100.5
    j.tick(in_videos=True, playing_video=False)      # Kodi rouvre la liste
    assert appels == []


def test_retour_accueil_efface_une_fois(monkeypatch) -> None:
    appels = []
    monkeypatch.setattr(listing_cache, "purge", lambda *a: appels.append(1) or 1)
    h = _Horloge()
    j = ListingCacheJanitor(delay=3.0, clock=h)
    j.tick(in_videos=False, playing_video=False)     # demarrage : rien a faire
    h.t = 10
    j.tick(in_videos=False, playing_video=False)
    assert appels == []
    j.tick(in_videos=True, playing_video=False)      # visite d'une liste
    h.t = 20
    j.tick(in_videos=False, playing_video=False)     # retour a l'accueil
    h.t = 22
    j.tick(in_videos=False, playing_video=False)
    assert appels == []
    h.t = 23.5
    j.tick(in_videos=False, playing_video=False)
    h.t = 40
    j.tick(in_videos=False, playing_video=False)
    assert appels == [1]


def _etat(monkeypatch, actif, dossier, nombre):
    monkeypatch.setattr(xbmc, "getCondVisibility", lambda c: actif)
    valeurs = {"Container.FolderPath": dossier, "Container.NumItems": nombre}
    monkeypatch.setattr(xbmc, "getInfoLabel", lambda n: valeurs.get(n, ""))


URL = "plugin://plugin.video.embycon/?url=%7Bserver%7D%2Fx&mode=GET_CONTENT&media_type=movies"


def test_progression_ouverture_dans_videos(monkeypatch) -> None:
    _etat(monkeypatch, True, URL, "0")
    assert listing_cache.show_progress_for(URL)


def test_pas_de_progression_pour_un_widget(monkeypatch) -> None:
    _etat(monkeypatch, False, "", "")
    assert not listing_cache.show_progress_for(URL)


def test_pas_de_progression_pour_un_rechargement_en_place(monkeypatch) -> None:
    _etat(monkeypatch, True, URL, "101")
    assert not listing_cache.show_progress_for(URL)


def test_progression_pour_une_sous_liste(monkeypatch) -> None:
    _etat(monkeypatch, True, URL, "101")
    assert listing_cache.show_progress_for(URL.replace("movies", "boxsets"))
