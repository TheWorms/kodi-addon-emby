"""v1.18.4/5 : date de sortie d'une collection = film le plus recent."""

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.collection_dates as cd  # noqa: E402

ENFANTS = {
    "bs-sw": [
        {"PremiereDate": "1977-05-25T00:00:00Z"},
        {"PremiereDate": "2019-12-18T00:00:00Z"},
    ],
    "bs-perso": [{"PremiereDate": "2008-01-01T00:00:00Z"}, {"ProductionYear": 2012}],
    "bs-vide": [],
}


def test_film_le_plus_recent() -> None:
    assert cd.latest_release(ENFANTS["bs-sw"]) == "2019-12-18"
    assert cd.latest_release(ENFANTS["bs-perso"]) == "2012"
    assert cd.latest_release([]) == ""


def test_calcul_en_parallele() -> None:
    actifs, pic = [0], [0]
    verrou = threading.Lock()

    def enfants(bid):
        with verrou:
            actifs[0] += 1
            pic[0] = max(pic[0], actifs[0])
        time.sleep(0.02)
        with verrou:
            actifs[0] -= 1
        return ENFANTS.get(bid, [])

    ids = ["bs-sw", "bs-perso", "bs-vide"] + ["x%d" % i for i in range(13)]
    dates = cd.compute_dates(ids, enfants, workers=8)
    assert dates["bs-sw"] == ("1977-05-25", "2019-12-18") and dates["bs-vide"] == ("", "")
    assert pic[0] > 1  # vraiment en parallele


def test_entrees_manquantes_ou_perimees() -> None:
    now = 1_000_000.0
    entrees = {
        "a": {"f": "2001", "d": "2020", "t": now - 10},
        "b": {"f": "", "d": "", "t": now - 10},
        "c": {"f": "2001", "d": "2019", "t": 0},
        "e": {"d": "2019", "t": now},  # ancien format (v1.18) : sans premier film
    }
    assert cd.missing_ids(entrees, ["a", "b", "c", "d", "e"], now) == ["c", "d", "e"]


def test_cache_disque(monkeypatch, tmp_path) -> None:
    chemin = str(tmp_path / "collection_dates.json")
    monkeypatch.setattr(cd, "_file_path", lambda: chemin)
    appels = []

    def enfants(bid):
        appels.append(bid)
        return ENFANTS.get(bid, [])

    dates = cd.collection_release_dates(["bs-sw", "bs-perso", "bs-vide"], enfants)
    assert dates == {"bs-sw": "2019-12-18", "bs-perso": "2012"}
    assert sorted(appels) == ["bs-perso", "bs-sw", "bs-vide"]
    # deuxieme appel : tout vient du disque, aucune requete (meme la vide)
    appels.clear()
    assert cd.collection_release_dates(["bs-sw", "bs-vide"], enfants) == {"bs-sw": "2019-12-18"}
    assert appels == []
    # nouvelle collection : seule elle est lue
    cd.collection_release_dates(["bs-sw", "bs-neuve"], enfants)
    assert appels == ["bs-neuve"]


def _details(identifiant, annee=None, date=None, type_="BoxSet"):
    return SimpleNamespace(id=identifiant, item_type=type_, year=annee, premiere_date=date)


def test_application_aux_elements(monkeypatch) -> None:
    monkeypatch.setattr(
        cd,
        "collection_release_dates",
        lambda ids, fetch_children=None, first=False: {"bs-sw": "2019-12-18", "bs-perso": "2012"},
    )
    sw = _details("bs-sw", 1977, "1977-05-25")
    perso = _details("bs-perso", None, "2008-01-01")
    film = _details("m1", 2000, "2000-01-01", type_="Movie")
    cd.apply_collection_dates([sw, perso, film])
    assert (sw.year, sw.premiere_date) == (2019, "2019-12-18")
    assert (perso.year, perso.premiere_date) == (2012, None)
    assert (film.year, film.premiere_date) == (2000, "2000-01-01")


def test_liste_sans_collection_aucune_requete(monkeypatch) -> None:
    def interdit(*_a, **_k):
        raise AssertionError("requete")

    monkeypatch.setattr(cd, "collection_release_dates", interdit)
    cd.apply_collection_dates([_details("m1", type_="Movie")])


def test_perimee_utilisee_par_les_widgets_rafraichie_par_le_service(monkeypatch, tmp_path) -> None:
    chemin = str(tmp_path / "collection_dates.json")
    monkeypatch.setattr(cd, "_file_path", lambda: chemin)
    cd._save(chemin, {"bs-sw": {"f": "1977-05-25", "d": "2015-12-16", "t": 0}})  # tres ancienne
    appels = []

    def enfants(bid):
        appels.append(bid)
        return ENFANTS.get(bid, [])

    # widget : la date perimee sert telle quelle, aucune attente
    assert cd.collection_release_dates(["bs-sw"], enfants) == {"bs-sw": "2015-12-16"}
    assert appels == []
    # service : rafraichit
    assert cd.collection_release_dates(["bs-sw"], enfants, allow_stale=False) == {"bs-sw": "2019-12-18"}
    assert appels == ["bs-sw"]


def test_date_d_ajout_conservee(monkeypatch) -> None:
    """v1.19.1 : la date d'ajout n'est plus remplacee par la date de sortie."""
    monkeypatch.setattr(
        cd,
        "collection_release_dates",
        lambda ids, fetch_children=None, first=False: {"bs-sw": "2019-12-18", "bs-perso": "2012"},
    )
    sw = _details("bs-sw", 1977, "1977-05-25")
    sw.date_added = "2024-03-01 10:00:00"
    perso = _details("bs-perso")
    perso.date_added = "2025-01-01 10:00:00"
    cd.apply_collection_dates([sw, perso])
    assert (sw.year, sw.premiere_date, sw.date_added) == (2019, "2019-12-18", "2024-03-01 10:00:00")
    assert (perso.year, perso.premiere_date) == (2012, None)


def test_ordre_croissant_date_du_premier_film(monkeypatch, tmp_path) -> None:
    """v1.19 : croissant = debut de la saga, decroissant = film le plus recent."""
    chemin = str(tmp_path / "collection_dates.json")
    monkeypatch.setattr(cd, "_file_path", lambda: chemin)
    enfants = lambda bid: ENFANTS.get(bid, [])  # noqa: E731
    assert cd.collection_release_dates(["bs-sw"], enfants) == {"bs-sw": "2019-12-18"}
    assert cd.collection_release_dates(["bs-sw"], enfants, first=True) == {"bs-sw": "1977-05-25"}

    sw = _details("bs-sw")
    sw.date_added = "2024-03-01 10:00:00"
    cd.apply_collection_dates([sw], ascending=True)
    assert (sw.year, sw.premiere_date) == (1977, "1977-05-25")


def test_sens_du_tri_des_collections() -> None:
    import lib.dir_functions as df

    def reglages(valeurs):
        return SimpleNamespace(getSetting=lambda k: valeurs.get(k, ""))

    assert df._collections_ascending(reglages({"list_sort-BoxSets": "9a"}), {"media_type": "boxsets"})
    assert not df._collections_ascending(reglages({"list_sort-BoxSets": "9d"}), {"media_type": "boxsets"})
    # v1.20.0 : un seul reglage pour la liste et le widget « Ajouts récents »
    assert df._collections_ascending(reglages({"list_sort-BoxSets": "2a"}), {"type": "recent_boxsets"})
    assert not df._collections_ascending(reglages({"list_sort-BoxSets": "0"}), {"media_type": "boxsets"})


# --- v1.20.1 : l'ordre EmbyCon resiste au tri « date d'ajout » du skin ------


class _Tag:
    def __init__(self, added, dbid):
        self.added = added
        self.dbid = dbid

    def setDateAdded(self, value):
        self.added = value

    def setDbId(self, value):
        self.dbid = value


class _ListItem:
    def __init__(self, label, added, dbid):
        self.label = label
        self.tag = _Tag(added, dbid)

    def getLabel(self):
        return self.label

    def getVideoInfoTag(self):
        return self.tag


def _gui(label, date, added, dbid):
    return SimpleNamespace(
        list_item=_ListItem(label, added, dbid), sort_date=date, sort_name=label, sort_added=added
    )


def _widget_kodi(items, descending):
    """Tri d'un widget Kodi par date d'ajout : cle « <date> <DBID> », tri stable."""
    ranges = sorted(
        items,
        key=lambda i: "%s %d" % (i.list_item.tag.added, i.list_item.tag.dbid),
        reverse=descending,
    )
    return [i.list_item.label for i in ranges]


def _collections():
    return [
        _gui("Star Wars", "1977-05-25", "2024-01-10 10:00:00", 300),
        _gui("Dune", "2021-09-15", "2025-06-01 10:00:00", 100),
        _gui("Alien", "1979-05-25", "2023-03-03 10:00:00", 200),
    ]


def test_widget_en_croissant_ou_decroissant_garde_l_ordre() -> None:
    import lib.dir_functions as df
    from lib.sort_options import sort_gui_items

    for sens_embycon, attendu in ((False, ["Star Wars", "Alien", "Dune"]), (True, ["Dune", "Alien", "Star Wars"])):
        liste = sort_gui_items(_collections(), "date", sens_embycon)
        df.freeze_order_for_skin(liste)
        # le widget d'Arctic etait en croissant (sens mal enregistre) ; un
        # autre skin peut etre en decroissant : meme resultat
        assert _widget_kodi(liste, descending=False) == attendu
        assert _widget_kodi(liste, descending=True) == attendu


def test_sans_correction_le_widget_imposait_son_ordre() -> None:
    from lib.sort_options import sort_gui_items

    liste = sort_gui_items(_collections(), "date", False)
    assert _widget_kodi(liste, descending=False) == ["Alien", "Star Wars", "Dune"]


def test_date_commune() -> None:
    from lib.sort_options import same_date_added

    assert same_date_added(["2024-01-10 10:00:00", "", "2025-06-01 10:00:00"]) == "2025-06-01 10:00:00"
    assert len(same_date_added([])) == 19
