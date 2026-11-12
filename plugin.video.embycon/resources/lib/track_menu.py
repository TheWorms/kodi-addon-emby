# Gnu General Public License - see LICENSE.TXT
"""v1.22.2 : fenetre de choix des pistes, au style du menu contextuel EmbyCon.

Remplace la fenetre de selection standard de Kodi pour le choix des pistes
audio et sous-titres : meme panneau noir que le clic droit, un titre, le
choix automatique deja selectionne (marque « AUTO ») et Retour qui le garde.
"""

from __future__ import annotations

from typing import cast

import xbmcaddon
import xbmcgui

from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)

ROW_HEIGHT = 50
MAX_ROWS = 8
SCREEN_HEIGHT = 720
PANEL_TOP_PAD = 10
HEADING_HEIGHT = 45
HINT_HEIGHT = 40
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92


def panel_layout(count: int) -> dict:
    """Positions verticales du panneau pour `count` lignes (centre a l'ecran)."""
    rows = max(1, min(count, MAX_ROWS))
    list_height = rows * ROW_HEIGHT
    height = PANEL_TOP_PAD + HEADING_HEIGHT + list_height + HINT_HEIGHT + PANEL_TOP_PAD
    top = (SCREEN_HEIGHT - height) // 2
    return {
        "top": top,
        "height": height,
        "heading_top": top + PANEL_TOP_PAD,
        "list_top": top + PANEL_TOP_PAD + HEADING_HEIGHT,
        "list_height": list_height,
        "hint_top": top + PANEL_TOP_PAD + HEADING_HEIGHT + list_height,
    }


def tag_auto(labels: list, auto_position: int, tag: str) -> list:
    """Ajoute l'etiquette « AUTO » au libelle du choix automatique."""
    tagged = list(labels)
    if 0 <= auto_position < len(tagged):
        tagged[auto_position] = "%s   [COLOR 99FFFFFF]%s[/COLOR]" % (
            tagged[auto_position],
            tag,
        )
    return tagged


class TrackMenu(xbmcgui.WindowXMLDialog):
    heading: str = ""
    hint: str = ""
    labels: list | None = None
    preselect: int = 0
    selected: int = -1

    def onInit(self) -> None:
        labels = self.labels or []
        layout = panel_layout(len(labels))
        background = self.getControl(3010)
        background.setPosition(340, layout["top"])
        background.setHeight(layout["height"])
        heading = cast(xbmcgui.ControlLabel, self.getControl(3001))
        heading.setPosition(354, layout["heading_top"])
        heading.setLabel(self.heading)
        hint = cast(xbmcgui.ControlLabel, self.getControl(3002))
        hint.setPosition(354, layout["hint_top"])
        hint.setLabel(self.hint)
        control = cast(xbmcgui.ControlList, self.getControl(3000))
        control.setPosition(354, layout["list_top"])
        control.setHeight(layout["list_height"])
        control.addItems([xbmcgui.ListItem(label) for label in labels])
        if 0 <= self.preselect < len(labels):
            control.selectItem(self.preselect)
        self.setFocus(control)

    def onAction(self, action: xbmcgui.Action) -> None:
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.selected = -1
            self.close()

    def onClick(self, controlId: int) -> None:
        if controlId == 3000:
            control = cast(xbmcgui.ControlList, self.getControl(3000))
            self.selected = control.getSelectedPosition()
            self.close()


def choose_track(
    heading: str, labels: list, preselect: int, hint: str, auto_tag: str
) -> int:
    """Affiche le menu ; position choisie, ou -1 (Retour : garder le choix auto)."""
    path = xbmcaddon.Addon().getAddonInfo("path")
    menu = TrackMenu("TrackMenu.xml", path, "default", "720p")
    menu.heading = heading.upper()
    menu.hint = hint
    menu.labels = tag_auto(labels, preselect, auto_tag)
    menu.preselect = preselect
    menu.doModal()
    selected = menu.selected
    del menu
    log.debug("Choix de piste : {0} -> {1}", heading, selected)
    return selected
