"""Tests v1.22.2 : menu des pistes au style du clic droit, recherche et
rechargement de liste apres une lecture."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.refresh_guard as rg  # noqa: E402
import lib.track_menu as tm  # noqa: E402

RACINE = Path(__file__).resolve().parents[1] / "plugin.video.embycon"


def test_panneau_centre_selon_le_nombre_de_pistes() -> None:
    deux = tm.panel_layout(2)
    assert deux["list_height"] == 100
    assert deux["top"] + deux["height"] // 2 in (359, 360)  # centre de l'ecran 720p
    assert deux["hint_top"] == deux["list_top"] + 100
    # au-dela de 8 pistes, la liste defile dans un panneau de 8 lignes
    assert tm.panel_layout(20)["list_height"] == 8 * 50
    assert tm.panel_layout(0)["list_height"] == 50


def test_etiquette_auto_sur_le_choix_automatique() -> None:
    labels = ["Anglais — TRUEHD 7.1", "Français (VFF) — EAC3 5.1"]
    tagged = tm.tag_auto(labels, 1, "AUTO")
    assert tagged[0] == labels[0]
    assert tagged[1].startswith("Français (VFF) — EAC3 5.1") and tagged[1].endswith(
        "AUTO[/COLOR]"
    )
    assert tm.tag_auto(labels, -1, "AUTO") == labels
    assert labels[1] == "Français (VFF) — EAC3 5.1"  # liste d'origine intacte


def test_fenetre_presente_avec_ses_controles() -> None:
    xml = (RACINE / "resources/skins/default/720p/TrackMenu.xml").read_text(
        encoding="utf-8"
    )
    for control in ('id="3010"', 'id="3001"', 'id="3000"', 'id="3002"'):
        assert control in xml
    assert 'type="list"' in xml  # pas de wraplist : pas de doublons a 2 pistes


def test_recherche_jamais_rechargee_apres_lecture() -> None:
    recherche = "plugin://plugin.video.embycon/?item_type=Movie&mode=NEW_SEARCH"
    assert not rg.can_refresh_after_playback(recherche)
    assert rg.can_refresh_after_playback(recherche + "&query=dune")
    assert rg.can_refresh_after_playback(
        "plugin://plugin.video.embycon/?mode=GET_CONTENT&media_type=movies&url=x"
    )
    assert not rg.can_refresh_after_playback("")
    assert not rg.can_refresh_after_playback("videodb://movies/titles/")


def test_textes_du_menu_traduits() -> None:
    fr = (RACINE / "resources/language/resource.language.fr_fr/strings.po").read_text(
        encoding="utf-8"
    )
    for texte in (
        "Piste audio",
        "Sous-titres",
        "OK : choisir · Retour : garder le choix « auto »",
    ):
        assert 'msgstr "%s"' % texte in fr
