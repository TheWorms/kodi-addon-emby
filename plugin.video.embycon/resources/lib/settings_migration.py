# Gnu General Public License - see LICENSE.TXT
"""v1.20.0 : conversion unique des reglages vers la nouvelle organisation.

Les reglages fusionnes ou dont les valeurs possibles ont change sont repris
depuis le fichier de reglages de l'utilisateur (addon_data/.../settings.xml),
lu directement : les anciens identifiants n'existent plus dans le
resources/settings.xml de l'addon.

Seules les valeurs que l'utilisateur avait modifiees sont converties (Kodi
marque les autres default="true") : les nouvelles valeurs par defaut
s'appliquent au reste.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from .sort_options import migrate_sort

LAYOUT_SETTING = "settings_layout"
LAYOUT_VERSION = "1.20.2"

SORT_CONTEXTS = ("Movies", "Series", "BoxSets", "InBoxSet", "InSeries")
DELETE_CHOICES = (100, 95, 90, 80)
NEXT_MOVIE_CHOICES = (30, 60, 90, 120, 180, 240, 300, 420, 600, 900)
# reglage -> (minimum, pas, maximum) des nouveaux selecteurs
GRID = {
    "auto_bitrate_min": (0, 500, 20000),
    "auto_bitrate_max": (0, 5000, 200000),
    "itemsPerPage": (0, 5, 200),
    "max_image_width": (0, 128, 4096),
    "cacheImagesOnScreenSaver_interval": (0, 5, 60),
    "random_movie_refresh_interval": (0, 5, 60),
}


def read_user_values(path: str) -> dict[str, str]:
    """Valeurs MODIFIEES par l'utilisateur ({id: valeur}) ; {} si pas de fichier."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {}
    values = {}
    for node in root.iter("setting"):
        setting_id = node.get("id")
        if not setting_id or node.get("default") == "true":
            continue
        values[setting_id] = (node.text or "").strip()
    return values


def _int(value: str | None, default: int) -> int:
    try:
        return int(float(value or ""))
    except ValueError:
        return default


def _nearest(value: int, choices: tuple) -> int:
    return min(choices, key=lambda c: (abs(c - value), c))


def _snap(value: int, low: int, step: int, high: int) -> int:
    value = max(low, min(high, value))
    return low + int(round((value - low) / float(step))) * step


def plan_migration(old: dict[str, str]) -> dict[str, str]:
    """Nouvelles valeurs a ecrire, d'apres les valeurs modifiees de l'utilisateur."""
    new: dict[str, str] = {}

    # tri : critere + sens reunis en une valeur (list_sort-<contexte>)
    for ctx in SORT_CONTEXTS:
        if "sort-" + ctx in old or "sort_order-" + ctx in old:
            new["list_sort-" + ctx] = migrate_sort(
                old.get("sort-" + ctx, _OLD_SORT_DEFAULTS[ctx][0]),
                old.get("sort_order-" + ctx, _OLD_SORT_DEFAULTS[ctx][1]),
                ctx,
            )

    # episode suivant : un seul choix, comme pour les films
    trigger = _int(old.get("play_next_trigger_time"), 0)
    if any(k in old for k in ("play_next_trigger_time", "promptPlayNextEpisodePercentage",
                              "promptPlayNextEpisodePercentage_prompt")):
        percent = _int(old.get("promptPlayNextEpisodePercentage"), 100)
        confirm = old.get("promptPlayNextEpisodePercentage_prompt", "true") == "true"
        if trigger > 0:
            mode = "1"
        elif percent < 100:
            mode = "1" if confirm else "2"
        else:
            mode = "0"
        new["next_episode_mode"] = mode
    if trigger > 0:
        new["play_next_trigger_time"] = str(_snap(trigger, 10, 5, 180))

    # AV1 : profil materiel + case « Forcer le transcodage av1 »
    if "hardware_profile" in old or "force_transcode_av1" in old:
        profile = old.get("hardware_profile", "0")
        if profile == "1" or old.get("force_transcode_av1") == "true":
            new["av1_transcode"] = "1"
        elif profile == "2":
            new["av1_transcode"] = "2"
        else:
            new["av1_transcode"] = "0"

    # choix fixes
    for key in ("promptDeleteEpisodePercentage", "promptDeleteMoviePercentage"):
        if key in old:
            new[key] = str(_nearest(_int(old[key], 100), DELETE_CHOICES))
    if "next_movie_trigger_time" in old:
        new["next_movie_trigger_time"] = str(
            _nearest(_int(old["next_movie_trigger_time"], 180), NEXT_MOVIE_CHOICES)
        )
    for key, (low, step, high) in GRID.items():
        if key in old:
            new[key] = str(_snap(_int(old[key], low), low, step, high))
    return new


# anciennes valeurs par defaut (sort-X, sort_order-X), pour un couple dont
# une seule moitie avait ete modifiee
_OLD_SORT_DEFAULTS = {
    "Movies": ("0", "0"),
    "Series": ("0", "0"),
    "BoxSets": ("4", "1"),
    "InBoxSet": ("9", "1"),
    "InSeries": ("9", "1"),
}


def plan_v1202(old: dict[str, str]) -> dict[str, str]:
    """v1.20.2 : films d'une collection du plus ancien au plus recent.

    L'ancien defaut (recent -> ancien) est remplace s'il n'avait pas ete
    choisi explicitement. Kodi re-applique une valeur stockee meme marquee
    default="true" : changer le defaut dans settings.xml ne suffit pas.
    """
    if "list_sort-InBoxSet" in old:
        return {}
    return {"list_sort-InBoxSet": "9a"}


def _version(value: str) -> tuple:
    try:
        return tuple(int(p) for p in value.split("."))
    except ValueError:
        return ()


def migrate_settings() -> None:
    """Appele au demarrage du service et de l'extension ; ne fait rien ensuite."""
    import xbmcaddon
    import xbmcvfs

    from .simple_logging import SimpleLogging

    log = SimpleLogging(__name__)
    try:
        addon = xbmcaddon.Addon()
        done = _version(addon.getSetting(LAYOUT_SETTING))
        if done >= _version(LAYOUT_VERSION):
            return
        profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        old = read_user_values(os.path.join(profile, "settings.xml"))
        changes = {} if done >= (1, 20) else plan_migration(old)
        if done < (1, 20, 2):
            changes.update(plan_v1202(dict(old, **changes)))
        for key, value in changes.items():
            addon.setSetting(key, value)
        addon.setSetting(LAYOUT_SETTING, LAYOUT_VERSION)
        log.info("Reglages convertis vers l'organisation {0} : {1}", LAYOUT_VERSION, changes)
    except Exception as err:
        log.error("Conversion des reglages impossible : {0}", err)
