"""Tests du profil matériel (v1.14) — stdlib pure, aucun stub Kodi requis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin.video.embycon" / "resources"))

from lib.hardware_profile import (  # noqa: E402
    PROFIL_AUTO,
    PROFIL_MANUEL,
    PROFIL_N2PLUS,
    av1_transcodage_force,
)


def test_profil_n2plus_force_le_transcodage_av1() -> None:
    assert av1_transcodage_force(PROFIL_N2PLUS) is True


def test_profil_manuel_ne_force_rien() -> None:
    assert av1_transcodage_force(PROFIL_MANUEL) is False


def test_profil_auto_depend_de_la_detection() -> None:
    assert av1_transcodage_force(PROFIL_AUTO, detecteur=lambda: True) is True
    assert av1_transcodage_force(PROFIL_AUTO, detecteur=lambda: False) is False


if __name__ == "__main__":
    test_profil_n2plus_force_le_transcodage_av1()
    test_profil_manuel_ne_force_rien()
    test_profil_auto_depend_de_la_detection()
    print("tests hardware_profile : OK")
