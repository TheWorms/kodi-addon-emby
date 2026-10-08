# Gnu General Public License - see LICENSE.TXT
"""Profil matériel de lecture (v1.14).

Détermine les capacités de lecture directe selon la plateforme
(ODROID-N2+ / Amlogic S922X sous CoreELEC). Python stdlib pur,
sans aucune dépendance externe.
"""
from __future__ import annotations

from typing import Callable

PROFIL_AUTO = 0
PROFIL_N2PLUS = 1
PROFIL_MANUEL = 2


def _lire_fichier(chemin: str) -> str:
    """Lit un fichier système, chaîne vide si inaccessible."""
    try:
        with open(chemin, encoding="utf-8", errors="ignore") as fichier:
            return fichier.read()
    except OSError:
        return ""


def detecter_odroid_n2plus() -> bool:
    """Vrai si la box est un ODROID-N2/N2+ (Amlogic S922X)."""
    modele = _lire_fichier("/proc/device-tree/model").replace("\x00", "")
    if "ODROID-N2" in modele:
        return True
    os_release = _lire_fichier("/etc/os-release")
    return "CoreELEC" in os_release and "odroid-n2" in os_release.lower()


def av1_transcodage_force(
    valeur_profil: int | None = None,
    detecteur: Callable[[], bool] | None = None,
) -> bool:
    """Vrai si l'AV1 doit être transcodé selon le profil matériel.

    Sur l'ODROID-N2+, le S922X ne décode pas l'AV1 : il faut demander
    le transcodage au serveur Emby.

    Args:
        valeur_profil: valeur du réglage ``hardware_profile``
            (0=Auto, 1=N2+, 2=Manuel) ; lue dans les réglages si absente.
        detecteur: fonction de détection de la plateforme,
            injectable pour les tests unitaires.
    """
    if valeur_profil is None:
        # import paresseux : le module reste testable sans Kodi
        import xbmcaddon

        valeur_profil = int(xbmcaddon.Addon().getSetting("hardware_profile") or "0")
    if valeur_profil == PROFIL_MANUEL:
        return False
    if valeur_profil == PROFIL_N2PLUS:
        return True
    return (detecteur or detecter_odroid_n2plus)()
