"""Tests v1.20.0 : nouvelle organisation des réglages et conversion unique."""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.settings_migration as mig  # noqa: E402
from lib.hardware_profile import av1_transcodage_force  # noqa: E402
from lib.sort_options import migrate_sort, parse_sort, server_sort  # noqa: E402

ADDON = Path(__file__).parent.parent / "plugin.video.embycon"
SETTINGS = ADDON / "resources" / "settings.xml"
PO = {
    lang: ADDON / "resources" / "language" / ("resource.language." + lang) / "strings.po"
    for lang in ("en_gb", "fr_fr")
}


# --- tri en une ligne ---------------------------------------------------------


def test_lecture_de_la_valeur_de_tri() -> None:
    assert parse_sort("9a") == ("9", False)
    assert parse_sort("4d") == ("4", True)
    assert parse_sort("0") is None
    assert parse_sort("") is None
    assert parse_sort("9") is None  # ancienne valeur non convertie : ordre serveur
    get = {"list_sort-Movies": "2d"}.get
    assert server_sort(lambda k: get(k, ""), "Movies") == ("SortName", "Descending")


def test_conversion_des_anciens_tris() -> None:
    assert migrate_sort("9", "0", "BoxSets") == "9a"  # le cas de Thib
    assert migrate_sort("4", "1", "BoxSets") == "4d"
    assert migrate_sort("3", "1", "Movies") == "9d"  # Année -> date de sortie
    assert migrate_sort("5", "0", "Movies") == "2a"  # Genre -> titre
    assert migrate_sort("7", "0", "Movies") == "7d"  # note : meilleure d'abord
    assert migrate_sort("0", "1", "Movies") == "0"
    assert migrate_sort("2", "1", "InSeries") == "2a"
    assert migrate_sort("4", "1", "InSeries") == "0"


# --- conversion unique -------------------------------------------------------

FICHIER = """<settings version="2">
    <setting id="sort-BoxSets">9</setting>
    <setting id="sort_order-BoxSets">0</setting>
    <setting id="sort-Movies" default="true">0</setting>
    <setting id="sort_order-InBoxSet">0</setting>
    <setting id="play_next_trigger_time">47</setting>
    <setting id="hardware_profile" default="true">0</setting>
    <setting id="force_transcode_av1">true</setting>
    <setting id="promptDeleteMoviePercentage">85</setting>
    <setting id="next_movie_trigger_time">150</setting>
    <setting id="max_image_width">400</setting>
    <setting id="username">thib</setting>
    <setting id="password" />
</settings>
"""


def test_valeurs_modifiees_seulement(tmp_path) -> None:
    chemin = tmp_path / "settings.xml"
    chemin.write_text(FICHIER, encoding="utf-8")
    valeurs = mig.read_user_values(str(chemin))
    assert valeurs["sort-BoxSets"] == "9"
    assert "sort-Movies" not in valeurs and "hardware_profile" not in valeurs
    assert valeurs["password"] == ""
    assert mig.read_user_values(str(tmp_path / "absent.xml")) == {}


def test_plan_de_conversion(tmp_path) -> None:
    chemin = tmp_path / "settings.xml"
    chemin.write_text(FICHIER, encoding="utf-8")
    plan = mig.plan_migration(mig.read_user_values(str(chemin)))
    assert plan == {
        "list_sort-BoxSets": "9a",
        "list_sort-InBoxSet": "9a",  # seul le sens avait changé
        "next_episode_mode": "1",
        "play_next_trigger_time": "45",
        "av1_transcode": "1",
        "promptDeleteMoviePercentage": "80",
        "next_movie_trigger_time": "120",
        "max_image_width": "384",
    }


def test_episode_suivant_converti() -> None:
    assert mig.plan_migration({"promptPlayNextEpisodePercentage": "90"})["next_episode_mode"] == "1"
    plan = mig.plan_migration(
        {"promptPlayNextEpisodePercentage": "90", "promptPlayNextEpisodePercentage_prompt": "false"}
    )
    assert plan["next_episode_mode"] == "2"
    assert mig.plan_migration({"play_next_trigger_time": "0"})["next_episode_mode"] == "0"
    assert mig.plan_migration({"play_next_trigger_time": "3"})["play_next_trigger_time"] == "10"
    assert mig.plan_migration({}) == {}


def test_av1_converti() -> None:
    assert mig.plan_migration({"hardware_profile": "2"})["av1_transcode"] == "2"
    assert mig.plan_migration({"hardware_profile": "1"})["av1_transcode"] == "1"
    assert mig.plan_migration({"force_transcode_av1": "false"})["av1_transcode"] == "0"
    assert av1_transcodage_force(1) is True
    assert av1_transcodage_force(2) is False
    assert av1_transcodage_force(0, lambda: True) is True


class _Addon:
    def __init__(self, profil, valeurs=None):
        self.profil = profil
        self.valeurs = dict(valeurs or {})
        self.ecrits = []

    def getSetting(self, cle):
        return self.valeurs.get(cle, "")

    def setSetting(self, cle, valeur):
        self.ecrits.append((cle, valeur))
        self.valeurs[cle] = valeur

    def getAddonInfo(self, _cle):
        return self.profil


def test_conversion_une_seule_fois(monkeypatch, tmp_path) -> None:
    (tmp_path / "settings.xml").write_text(FICHIER, encoding="utf-8")
    addon = _Addon(str(tmp_path))
    monkeypatch.setattr(sys.modules["xbmcaddon"], "Addon", lambda: addon, raising=False)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "translatePath", lambda p: p, raising=False)
    mig.migrate_settings()
    assert ("list_sort-BoxSets", "9a") in addon.ecrits
    assert addon.ecrits[-1] == ("settings_layout", mig.LAYOUT_VERSION)
    nombre = len(addon.ecrits)
    mig.migrate_settings()
    assert len(addon.ecrits) == nombre


# --- cohérence de settings.xml -------------------------------------------------


def _po_ids(path: Path) -> dict:
    texte = path.read_text(encoding="utf-8")
    out = {}
    for bloc in texte.split("\n\n"):
        m = re.search(r'msgctxt "#(\d+)"', bloc)
        if m:
            msgstr = re.search(r'msgstr "(.*)"', bloc)
            out[m.group(1)] = msgstr.group(1) if msgstr else ""
    return out


def test_chaines_et_dependances() -> None:
    racine = ET.parse(SETTINGS).getroot()
    en, fr = _po_ids(PO["en_gb"]), _po_ids(PO["fr_fr"])
    references = set()
    for el in racine.iter():
        for attr in ("label", "help"):
            if el.get(attr):
                references.add(el.get(attr))
        if el.tag in ("heading", "formatlabel") and el.text:
            references.add(el.text.strip())
    manquantes = sorted(r for r in references if r not in en or r not in fr)
    assert manquantes == []
    non_traduites = sorted(r for r in references if int(r) >= 30600 and not fr[r])
    assert non_traduites == []

    ids = {s.get("id") for s in racine.iter("setting")}
    assert len(ids) == len(list(racine.iter("setting")))
    for s in racine.iter("setting"):
        assert s.get("parent") is None or s.get("parent") in ids
        for cond in s.iter("condition"):
            assert cond.get("setting") in ids


def test_reglages_lus_par_le_code_existent() -> None:
    ids = {s.get("id") for s in ET.parse(SETTINGS).getroot().iter("setting")}
    motif = re.compile(r'(?:get|set)Setting\(\s*["\']([^"\']+)["\']')
    sources = list((ADDON / "resources" / "lib").glob("*.py")) + [ADDON / "service.py", ADDON / "default.py"]
    absents = set()
    for fichier in sources:
        for cle in motif.findall(fichier.read_text(encoding="utf-8")):
            if cle not in ids and not cle.startswith("saved_user_password_"):
                absents.add(cle)
    # anciens identifiants lus uniquement par la conversion (fichier utilisateur)
    assert absents == set()


def test_sept_menus() -> None:
    racine = ET.parse(SETTINGS).getroot()
    assert [c.get("id") for c in racine.iter("category")] == [
        "lecture", "enchainements", "listes", "fiches", "hasard", "serveur", "avance"
    ]
    visibles = [s for s in racine.iter("setting") if s.findtext("visible") != "false"]
    assert len(visibles) == 94  # v1.21.0 : lecture continue en aleatoire


# --- v1.20.2 : films d'une collection, du plus ancien au plus recent --------


def test_collection_ancien_vers_recent(monkeypatch, tmp_path) -> None:
    # installation deja en 1.20 : ancien defaut 9d (marque default="true")
    (tmp_path / "settings.xml").write_text(
        '<settings version="2"><setting id="list_sort-InBoxSet" default="true">9d</setting></settings>',
        encoding="utf-8",
    )
    addon = _Addon(str(tmp_path), {"settings_layout": "1.20", "list_sort-InBoxSet": "9d"})
    monkeypatch.setattr(sys.modules["xbmcaddon"], "Addon", lambda: addon, raising=False)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "translatePath", lambda p: p, raising=False)
    mig.migrate_settings()
    assert addon.ecrits == [("list_sort-InBoxSet", "9a"), ("settings_layout", "1.20.2")]


def test_choix_explicite_conserve() -> None:
    assert mig.plan_v1202({"list_sort-InBoxSet": "9d"}) == {}
    assert mig.plan_v1202({}) == {"list_sort-InBoxSet": "9a"}
