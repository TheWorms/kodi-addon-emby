# Gnu General Public License - see LICENSE.TXT
"""v1.22.1 : masquer les collections deja vues dans les widgets.

Une collection est « deja vue » quand Emby la marque comme lue (tous ses
films vus) ou qu'il ne lui reste aucun element non vu. Le filtre ne
s'applique qu'aux widgets (accueil) : la liste Collections, ouverte en plein
ecran, continue d'afficher toutes les collections.

Module sans dependance Kodi : testable hors Kodi.
"""

from __future__ import annotations

from typing import Callable

SETTING = "hide_watched_collections"


def is_watched(gui_item) -> bool:
    """Vrai si toute la collection a ete vue."""
    if getattr(gui_item, "play_count", 0):
        return True
    unplayed = getattr(gui_item, "unplayed_items", None)
    total = getattr(gui_item, "total_items", None)
    return unplayed == 0 and bool(total)


def drop_watched(items: list) -> list:
    """Retire les collections deja vues (l'ordre est conserve)."""
    return [item for item in items if not is_watched(item)]


def hide_in_widget(
    get_setting: Callable[[str], str], library_window_open: bool
) -> bool:
    """Le reglage est actif et la liste est chargee par un widget."""
    return get_setting(SETTING) == "true" and not library_window_open
