"""Tests v1.22.1 : collections deja vues masquees dans les widgets."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.watched_filter as wf  # noqa: E402
from lib.item_functions import GuiItem  # noqa: E402

RACINE = Path(__file__).resolve().parents[1] / "plugin.video.embycon"


def _collection(nom, play_count=0, unplayed=None, total=None):
    return SimpleNamespace(
        nom=nom, play_count=play_count, unplayed_items=unplayed, total_items=total
    )


def test_collection_vue_selon_emby() -> None:
    assert wf.is_watched(_collection("Wicked", play_count=1))
    assert wf.is_watched(_collection("Kolory", unplayed=0, total=2))


def test_collection_pas_encore_vue() -> None:
    assert not wf.is_watched(_collection("Wicked", unplayed=1, total=2))
    assert not wf.is_watched(_collection("Inconnue"))
    # collection vide (aucun film) : pas consideree comme vue
    assert not wf.is_watched(_collection("Vide", unplayed=0, total=0))


def test_seules_les_collections_vues_disparaissent_dans_l_ordre() -> None:
    liste = [
        _collection("Wicked", unplayed=1, total=2),
        _collection("Kolory", play_count=1),
        _collection("Chasse gardée", unplayed=2, total=2),
        _collection("Cocorico", unplayed=0, total=1),
    ]
    assert [c.nom for c in wf.drop_watched(liste)] == ["Wicked", "Chasse gardée"]


def test_seulement_dans_les_widgets_et_si_le_reglage_est_actif() -> None:
    actif = {"hide_watched_collections": "true"}.get
    inactif = {"hide_watched_collections": "false"}.get
    assert wf.hide_in_widget(lambda k: actif(k, ""), library_window_open=False)
    assert not wf.hide_in_widget(lambda k: actif(k, ""), library_window_open=True)
    assert not wf.hide_in_widget(lambda k: inactif(k, ""), library_window_open=False)


def test_gui_item_porte_les_compteurs() -> None:
    item = GuiItem(url="u", list_item=None, is_folder=True)
    assert item.unplayed_items is None and item.total_items is None
    assert not wf.is_watched(item)


def test_reglage_present_desactive_par_defaut() -> None:
    xml = (RACINE / "resources" / "settings.xml").read_text(encoding="utf-8")
    debut = xml.index('<setting id="hide_watched_collections"')
    bloc = xml[debut : xml.index("</setting>", debut)]
    assert "<default>false</default>" in bloc
    fr = (RACINE / "resources/language/resource.language.fr_fr/strings.po").read_text(
        encoding="utf-8"
    )
    assert 'msgstr "Masquer les collections déjà vues dans les widgets"' in fr
