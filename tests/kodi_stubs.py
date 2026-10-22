"""Stubs minimaux des modules Kodi pour tester les fonctions pures (v1.15).

La CI n'installe ni Kodi ni kodistubs : on remplace xbmc* par des MagicMock
avant d'importer les modules de l'addon. Seules les fonctions sans effet de
bord Kodi sont testees ainsi.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

RESOURCES = Path(__file__).parent.parent / "plugin.video.embycon" / "resources"


def install() -> None:
    for name in ("xbmc", "xbmcgui", "xbmcaddon", "xbmcvfs", "xbmcplugin"):
        if name not in sys.modules:
            sys.modules[name] = MagicMock(name=name)
    # WindowXMLDialog doit rester une vraie classe pour pouvoir en heriter
    sys.modules["xbmcgui"].WindowXMLDialog = type("WindowXMLDialog", (), {})
    sys.modules["xbmcgui"].WindowXML = type("WindowXML", (), {})
    sys.modules["xbmc"].Player = type("Player", (), {})
    sys.modules["xbmc"].Monitor = type("Monitor", (), {})
    if str(RESOURCES) not in sys.path:
        sys.path.insert(0, str(RESOURCES))
