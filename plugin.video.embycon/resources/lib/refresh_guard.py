# Gnu General Public License - see LICENSE.TXT
"""v1.22.2 : listes qu'on peut recharger apres une lecture.

Une liste de resultats de recherche (mode NEW_SEARCH sans texte dans
l'adresse) redemande le texte au clavier quand elle est rechargee : la
recharger au retour d'une lecture rouvrait le clavier en plein chargement
et pouvait figer puis faire planter Kodi. Ces listes ne sont pas rechargees.

Module sans dependance Kodi : testable hors Kodi.
"""

from __future__ import annotations


def can_refresh_after_playback(folder_path: str) -> bool:
    """La liste affichee est-elle une liste EmbyCon rechargeable sans question ?"""
    if not folder_path or "plugin.video.embycon" not in folder_path:
        return False
    lowered = folder_path.lower()
    if "mode=new_search" in lowered and "query=" not in lowered:
        return False
    return True
