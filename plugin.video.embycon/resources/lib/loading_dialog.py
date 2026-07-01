# Gnu General Public License - see LICENSE.TXT
from __future__ import annotations

import xbmcgui

from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)


class LoadingIndicator:
    """Indicateur de chargement (boite de progression Kodi standard).

    Expose l'interface create/update/close pour rester transparent vis-a-vis
    du reste du code. Tout echec retombe silencieusement sur l'absence
    d'indicateur (jamais bloquant).

    Note : l'ancien spinner vert custom (EmbyLoadingDialog / WindowXMLDialog)
    a ete retire. Affiche via .show() pendant la construction du repertoire,
    il entrait en conflit avec le rendu de la liste (fenetres multiples en
    navigation rapide -> "Window id does not exist" et gel de l'interface).
    Le parametre de style est conserve pour compatibilite mais ignore.
    """

    def __init__(self, style: str = "0") -> None:
        self.style = style
        self.dialog = None

    def create(self, heading: str, message: str = "") -> None:
        try:
            self.dialog = xbmcgui.DialogProgress()
            self.dialog.create(heading, message)
        except Exception as e:
            log.error("LoadingIndicator create failed: {0}", e)
            self.dialog = None

    def update(self, percent: int, message: str = "") -> None:
        try:
            if self.dialog is not None:
                self.dialog.update(percent, message)
        except Exception:
            pass

    def close(self) -> None:
        try:
            if self.dialog is not None:
                self.dialog.close()
        except Exception:
            pass
        self.dialog = None
