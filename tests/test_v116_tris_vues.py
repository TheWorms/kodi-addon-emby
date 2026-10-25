"""Tests v1.16 « Tris & vues »."""

import json
import sys
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

from lib.sort_options import (  # noqa: E402
    client_sort,
    recent_newest_first,
    server_sort,
    sort_context,
    sort_gui_items,
)
from lib.view_memory import ViewStore, category_chain, is_view_id  # noqa: E402

DEFAUTS_V116 = {
    "sort-BoxSets": "4",
    "sort_order-BoxSets": "1",
    "sort-InBoxSet": "9",
    "sort_order-InBoxSet": "1",
    "sort-InSeries": "9",
    "sort_order-InSeries": "1",
    "sort_order-RecentMovies": "0",
    "sort_order-RecentSeries": "0",
    "sort-Movies": "0",
    "sort-Series": "0",
}


def reglages(**surcharges):
    valeurs = dict(DEFAUTS_V116)
    valeurs.update({k.replace("__", "-"): v for k, v in surcharges.items()})
    return lambda cle: valeurs.get(cle, "")


# --- contextes ------------------------------------------------------------


def test_contextes() -> None:
    assert sort_context("movies") == "Movies"
    assert sort_context("tvshows") == "Series"
    assert sort_context("boxsets") == "BoxSets"
    assert sort_context("BoxSet") == "InBoxSet"
    assert sort_context("Series") == "InSeries"
    assert sort_context("Season") == "InSeries"
    assert sort_context("Episodes") is None
    assert sort_context(None) is None


# --- defauts demandes -------------------------------------------------------


def test_collections_par_date_d_ajout_plus_recent_d_abord() -> None:
    assert server_sort(reglages(), "BoxSets") == ("DateCreated,SortName", "Descending")


def test_contenu_collection_par_date_de_sortie_plus_recent_d_abord() -> None:
    assert server_sort(reglages(), "InBoxSet") == (
        "PremiereDate,ProductionYear,SortName",
        "Descending",
    )


def test_contenu_collection_n_herite_plus_de_la_liste() -> None:
    get = reglages(**{"sort__InBoxSet": "2", "sort_order__InBoxSet": "0"})
    assert server_sort(get, "InBoxSet") == ("SortName", "Ascending")
    assert server_sort(get, "BoxSets") == ("DateCreated,SortName", "Descending")


def test_mediatheques_non_definies_gardent_l_ordre_serveur() -> None:
    assert server_sort(reglages(), "Movies") is None
    assert server_sort(reglages(), "Series") is None


def test_dans_une_serie_tri_client_par_date_decroissante() -> None:
    assert client_sort(reglages(), "InSeries") == ("date", True)
    assert client_sort(reglages(**{"sort__InSeries": "0"}), "InSeries") is None
    assert server_sort(reglages(), "InSeries") is None


def test_recents_plus_recent_d_abord_par_defaut() -> None:
    assert recent_newest_first(reglages(), "RecentMovies") is True
    get = reglages(**{"sort_order__RecentSeries": "1"})
    assert recent_newest_first(get, "RecentSeries") is False


# --- tri client -------------------------------------------------------------


def _ep(nom, date, saison, episode):
    return SimpleNamespace(
        sort_name=nom, sort_date=date, sort_index=(saison, episode), label=nom
    )


def test_tri_client_par_date_decroissante() -> None:
    items = [
        _ep("S1E1", "2019-01-01", 1, 1),
        _ep("S1E2", "2019-01-08", 1, 2),
        _ep("Tous les episodes", "", 0, 0),
        _ep("S2E1", "2020-03-01", 2, 1),
    ]
    tries = sort_gui_items(items, "date", True)
    assert [i.label for i in tries] == ["S2E1", "S1E2", "S1E1", "Tous les episodes"]


def test_tri_client_meme_date_departage_par_numero() -> None:
    items = [_ep("E2", "2019", 1, 2), _ep("E1", "2019", 1, 1)]
    assert [i.label for i in sort_gui_items(items, "date", False)] == ["E1", "E2"]


def test_tri_client_par_nom() -> None:
    items = [_ep("b", "", 0, 0), _ep("A", "", 0, 0)]
    assert [i.label for i in sort_gui_items(items, "name", False)] == ["A", "b"]


# --- vues par categorie -----------------------------------------------------


def _chemin(url_emby, media_type, mode="GET_CONTENT"):
    return (
        "plugin://plugin.video.embycon/?url="
        + urllib.parse.quote(url_emby)
        + "&mode="
        + mode
        + "&media_type="
        + media_type
    )


def test_categorie_mediatheque_films() -> None:
    chemin = _chemin("{server}/emby/Users/{userid}/Items?ParentId=lib1&IncludeItemTypes=Movie", "movies")
    assert category_chain(chemin) == ["movies@lib1", "movies"]


def test_categorie_collection_separee_des_films() -> None:
    chemin = _chemin("{server}/emby/Users/{userid}/items?ParentId=bs9", "BoxSet")
    assert category_chain(chemin) == ["boxset"]


def test_categories_serie() -> None:
    assert category_chain(_chemin("{server}/emby/Shows/x/Seasons", "Series")) == ["seasons"]
    assert category_chain(_chemin("{server}/emby/Shows/x/Episodes", "Season")) == ["episodes"]
    assert category_chain(_chemin("{server}/x", "boxsets")) == ["sets"]


def test_categories_menus_et_hors_embycon() -> None:
    assert category_chain("plugin://plugin.video.embycon/") == ["menus"]
    assert category_chain("plugin://plugin.video.embycon/?mode=GENRES&item_type=movie") == ["genres"]
    assert category_chain("videodb://movies/titles/") == []
    assert category_chain("") == []


def test_parent_none_ignore() -> None:
    chemin = _chemin("{server}/emby/Users/{userid}/Items?ParentId=none", "movies")
    assert category_chain(chemin) == ["movies"]


def test_ids_de_vue() -> None:
    assert is_view_id(50) and is_view_id(59) and is_view_id(500) and is_view_id(527)
    assert not is_view_id(9000) and not is_view_id(49) and not is_view_id(600)


def test_store_memorise_par_categorie(tmp_path) -> None:
    store = ViewStore(str(tmp_path / "views.json"))
    store._write({})
    store.save(["movies@lib1", "movies"], 510)
    store.save(["boxset"], 55)
    assert store.lookup(["movies@lib1", "movies"]) == "510"
    # liste globale : repli sur la categorie generale
    assert store.lookup(["movies"]) == "510"
    # une autre mediatheque Films herite du defaut general...
    assert store.lookup(["movies@lib2", "movies"]) == "510"
    # ...mais changer sa vue n'ecrase ni lib1 ni le defaut general
    store.save(["movies@lib2", "movies"], 54)
    assert store.lookup(["movies@lib1", "movies"]) == "510"
    assert store.lookup(["movies"]) == "510"
    assert store.lookup(["boxset"]) == "55"
    store.forget(["boxset"])
    assert store.lookup(["boxset"]) is None
    data = json.loads((tmp_path / "views.json").read_text(encoding="utf-8"))
    assert data["version"] == 1
    store.clear()
    assert store.lookup(["movies"]) is None


def test_store_fichier_corrompu(tmp_path) -> None:
    chemin = tmp_path / "views.json"
    chemin.write_text("{pas du json", encoding="utf-8")
    assert ViewStore(str(chemin)).lookup(["movies"]) is None


# --- moniteur de vues (simulation sans Kodi) ---------------------------------


class FakeKodi:
    """Etat minimal de Kodi pilote pas a pas par waitForAbort."""

    def __init__(self, script, steps) -> None:
        self.now = 1000.0
        self.step = 0
        self.steps = steps
        self.script = script  # {pas: callable(self)}
        self.path = ""
        self.view = 50  # vue visible (= id du controle focalise)
        self.applied = []

    # xbmc.Monitor
    def waitForAbort(self, seconds) -> bool:
        self.now += seconds
        self.step += 1
        action = self.script.get(self.step)
        if action:
            action(self)
        return False

    def abortRequested(self) -> bool:
        return self.step >= self.steps

    # infos
    def getCondVisibility(self, cond: str) -> bool:
        if cond == "Window.IsActive(videos)":
            return True
        if cond == "Container.IsUpdating":
            return False
        if cond.startswith("Control.IsVisible("):
            return int(cond[len("Control.IsVisible(") : -1]) == self.view
        return False

    def getInfoLabel(self, label: str) -> str:
        return self.path if label == "Container.FolderPath" else ""

    def executebuiltin(self, cmd: str) -> None:
        if cmd.startswith("Container.SetViewMode("):
            self.view = int(cmd[len("Container.SetViewMode(") : -1])
            self.applied.append(self.view)


def _run_monitor(monkeypatch, tmp_path, kodi, auto="true"):
    import lib.view_memory as vm

    monkeypatch.setattr(vm.xbmc, "Monitor", lambda: kodi, raising=False)
    monkeypatch.setattr(vm.xbmc, "getCondVisibility", kodi.getCondVisibility, raising=False)
    monkeypatch.setattr(vm.xbmc, "getInfoLabel", kodi.getInfoLabel, raising=False)
    monkeypatch.setattr(vm.xbmc, "executebuiltin", kodi.executebuiltin, raising=False)
    monkeypatch.setattr(
        vm.xbmcgui, "Window", lambda _id: SimpleNamespace(getFocusId=lambda: kodi.view), raising=False
    )
    monkeypatch.setattr(
        vm.xbmcaddon,
        "Addon",
        lambda: SimpleNamespace(getSetting=lambda _k: auto, getAddonInfo=lambda _k: str(tmp_path)),
        raising=False,
    )
    monkeypatch.setattr(vm.time, "time", lambda: kodi.now)
    store = ViewStore(str(tmp_path / "views.json"))
    store._write({})
    monitor = vm.ViewMonitor.__new__(vm.ViewMonitor)
    monitor.stop_thread = False
    monitor.store = store
    monitor._warned_skin = False
    return monitor, store


LIB1 = _chemin("{server}/emby/Users/{userid}/Items?ParentId=lib1", "movies")
COLL = _chemin("{server}/emby/Users/{userid}/items?ParentId=bs9", "BoxSet")


def test_vue_appliquee_puis_reimposee_si_le_skin_la_change(monkeypatch, tmp_path) -> None:
    def ouvrir(k):
        k.path = LIB1

    def skin_force(k):
        k.view = 50  # le skin reimpose sa vue juste apres l'application

    kodi = FakeKodi({1: ouvrir, 3: skin_force}, steps=20)
    monitor, store = _run_monitor(monkeypatch, tmp_path, kodi)
    store.save(["movies@lib1", "movies"], 510)
    monitor.run()
    assert kodi.applied[:2] == [510, 510]
    assert kodi.view == 510
    # la vue imposee par le skin pendant le chargement n'est PAS memorisee
    assert store.lookup(["movies@lib1"]) == "510"


def test_changement_utilisateur_memorise_pour_la_categorie(monkeypatch, tmp_path) -> None:
    def ouvrir_lib(k):
        k.path = LIB1

    def utilisateur_change(k):
        k.view = 54

    def ouvrir_collection(k):
        k.path = COLL
        k.view = 50

    kodi = FakeKodi({1: ouvrir_lib, 15: utilisateur_change, 20: ouvrir_collection}, steps=40)
    monitor, store = _run_monitor(monkeypatch, tmp_path, kodi)
    monitor.run()
    assert store.lookup(["movies@lib1"]) == "54"
    assert store.lookup(["movies"]) == "54"
    # la collection n'a rien herite : categorie distincte
    assert store.lookup(["boxset"]) is None


def test_memorisation_auto_desactivee(monkeypatch, tmp_path) -> None:
    def ouvrir(k):
        k.path = LIB1

    def utilisateur_change(k):
        k.view = 54

    kodi = FakeKodi({1: ouvrir, 15: utilisateur_change}, steps=25)
    monitor, store = _run_monitor(monkeypatch, tmp_path, kodi, auto="false")
    monitor.run()
    assert store.lookup(["movies@lib1", "movies"]) is None



# --- v1.18.2 : contenu d'une collection trie aussi cote client ----------------


def test_collection_tri_client_par_date() -> None:
    assert client_sort(reglages(), "InBoxSet") == ("date", True)
    assert client_sort(reglages(**{"sort__InBoxSet": "4"}), "InBoxSet") == ("added", True)
    assert client_sort(reglages(**{"sort__InBoxSet": "0"}), "InBoxSet") is None
    # dans une serie, seuls date et nom sont proposes
    assert client_sort(reglages(**{"sort__InSeries": "4"}), "InSeries") is None


def test_collection_ordre_serveur_corrige() -> None:
    films = [
        SimpleNamespace(label="B", sort_date="2002-05-16", sort_name="b", sort_index=(0, 0)),
        SimpleNamespace(label="C", sort_date="2005-05-19", sort_name="c", sort_index=(0, 0)),
        SimpleNamespace(label="A", sort_date="1999-05-19", sort_name="a", sort_index=(0, 0)),
    ]
    assert [f.label for f in sort_gui_items(films, "date", True)] == ["C", "B", "A"]
    assert [f.label for f in sort_gui_items(films, "date", False)] == ["A", "B", "C"]


def test_tri_par_ajout_et_note() -> None:
    films = [
        SimpleNamespace(label="x", sort_added="2026-01-02 10:00:00", sort_rating=6.1),
        SimpleNamespace(label="y", sort_added="2026-03-01 10:00:00", sort_rating=8.4),
    ]
    assert [f.label for f in sort_gui_items(films, "added", True)] == ["y", "x"]
    assert [f.label for f in sort_gui_items(films, "rating", True)] == ["y", "x"]


def test_sort_emby_items() -> None:
    from lib.sort_options import sort_emby_items

    items = [
        {"Id": "c", "PremiereDate": "2005-05-19T00:00:00Z", "SortName": "C"},
        {"Id": "a", "ProductionYear": 1999, "SortName": "A"},
        {"Id": "b", "PremiereDate": "2002-05-16T00:00:00Z", "SortName": "B"},
        {"Id": "z", "SortName": "Z"},  # sans date : a la fin en croissant
    ]
    assert [i["Id"] for i in sort_emby_items(items, "0")] == ["a", "b", "c", "z"]
    assert [i["Id"] for i in sort_emby_items(items, "2")] == ["a", "b", "c", "z"]
    assert [i["Id"] for i in sort_emby_items(items, "1")] == ["c", "b", "a", "z"]
