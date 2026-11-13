"""Stubs minimaux des modules Kodi pour tester les fonctions pures (v1.15).

La CI n'installe ni Kodi ni kodistubs : on remplace xbmc* par des MagicMock
avant d'importer les modules de l'addon. Seules les fonctions sans effet de
bord Kodi sont testees ainsi.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

RESOURCES = Path(__file__).parent.parent / "plugin.video.embycon" / "resources"


def _plain(module, full_name: str, name: str) -> None:
    mock = MagicMock(name=full_name)

    def stub(*args, **kwargs):
        return mock(*args, **kwargs)

    stub.mock = mock
    setattr(module, name, stub)


def _mock_class(full_name: str, name: str) -> type:
    """v1.22.6 : vraie classe (on peut en heriter, et un monkeypatch se
    restaure sans la supprimer sous Python 3.11) dont les instances se
    comportent comme un MagicMock (methodes et valeurs de retour factices)."""
    backing = MagicMock(name=full_name)

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __getattr__(self, attr):
        return getattr(backing.return_value, attr)

    return type(name, (), {"__init__": __init__, "__getattr__": __getattr__})


def install() -> None:
    for name in ("xbmc", "xbmcgui", "xbmcaddon", "xbmcvfs", "xbmcplugin"):
        if name not in sys.modules:
            sys.modules[name] = MagicMock(name=name)
    # WindowXMLDialog doit rester une vraie classe pour pouvoir en heriter
    sys.modules["xbmcgui"].WindowXMLDialog = type("WindowXMLDialog", (), {})
    sys.modules["xbmcgui"].WindowXML = type("WindowXML", (), {})
    # v1.22.6 : idem pour le lecteur et le moniteur de Kodi
    for name in ("Player", "Monitor"):
        setattr(sys.modules["xbmc"], name, _mock_class("xbmc." + name, name))
    # v1.21.6 : fonctions et classes Kodi patchees par les tests = de simples
    # fonctions Python, pas des enfants MagicMock. Sous Python 3.11, restaurer
    # un enfant MagicMock apres un monkeypatch le SUPPRIME (AttributeError:
    # Window dans la CI GitHub, selon l'ordre des tests).
    for module, names in (
        ("xbmcgui", ("Window", "Dialog", "DialogProgress")),
        ("xbmc", ("executebuiltin", "getCondVisibility", "getInfoLabel", "sleep")),
        ("xbmcaddon", ("Addon",)),
        ("xbmcvfs", ("translatePath",)),
    ):
        for name in names:
            _plain(sys.modules[module], module + "." + name, name)
    if str(RESOURCES) not in sys.path:
        sys.path.insert(0, str(RESOURCES))
