# Gnu General Public License - see LICENSE.TXT
from __future__ import annotations

import xbmcaddon
import xbmcplugin
import xbmcgui

import urllib.parse
import sys
import re
import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from .datamanager import DataManager
from .downloadutils import DownloadUtils
from .translation import string_load
from .loading_dialog import LoadingIndicator
from .simple_logging import SimpleLogging
from .item_functions import (
    add_gui_item,
    ItemDetails,
    GuiItem,
    GuiOptions,
    DisplayOptions,
)
from .tracking import timer
from .kodi_utils import HomeWindow
from .sort_options import (
    sort_context,
    server_sort,
    client_sort,
    sort_gui_items,
    describe_order,
    rank_stamps,
)
from .collection_dates import apply_collection_dates

log = SimpleLogging(__name__)


@dataclass
class DirectoryResult:
    """Represents the result of processing a directory.

    Attributes:
        dir_items: List of GuiItem objects
        detected_type: The detected media type, if any
        total_records: Total number of records available
    """

    dir_items: list[GuiItem]
    detected_type: str | None
    total_records: int


@timer
def get_content(url: str, params: dict[str, str]) -> int:
    log.debug("== ENTER: getContent ==")

    default_sort = params.get("sort", "")
    media_type = params.get("media_type", None)
    if not media_type:
        xbmcgui.Dialog().ok(string_load(30135), string_load(30139))

    log.debug("URL: {0}", url)
    log.debug("MediaType: {0}", media_type)
    pluginhandle = int(sys.argv[1])

    settings = xbmcaddon.Addon()
    # determine view type, map it from media type to view type
    view_type = ""
    content_type = ""
    media_type = str(media_type).lower().strip()
    if media_type.startswith("movie"):
        view_type = "Movies"
        content_type = "movies"
    elif media_type == "musicalbums":
        view_type = "Albums"
        content_type = "albums"
    elif media_type == "musicartists":
        view_type = "Artists"
        content_type = "artists"
    elif media_type == "musicartist":
        view_type = "Albums"
        content_type = "albums"
    elif media_type == "music" or media_type == "audio" or media_type == "musicalbum":
        view_type = "Music"
        content_type = "songs"
    elif media_type.startswith("boxsets"):
        view_type = "Movies"
        content_type = "sets"
    elif media_type.startswith("boxset"):
        view_type = "BoxSets"
        content_type = "movies"
    elif media_type == "tvshows":
        view_type = "Series"
        content_type = "tvshows"
    elif media_type == "series":
        view_type = "Seasons"
        content_type = "seasons"
    elif media_type == "season" or media_type == "episodes":
        view_type = "Episodes"
        content_type = "episodes"
    elif media_type == "playlists":
        view_type = "Playlists"
    elif media_type == "playlist":
        view_type = "Playlist"

    log.debug(
        "media_type:{0} content_type:{1} view_type:{2} ",
        media_type,
        content_type,
        view_type,
    )

    # EmbyCon FR: tri cote serveur par mediatheque (Films / Series / Collections).
    # Applique uniquement si l'URL ne porte pas deja de SortBy explicite (parcours
    # simple d'une mediatheque), afin de ne pas ecraser les noeuds speciaux
    # (Ajouts recents, En cours, Vus recemment...) qui fixent deja leur propre tri.
    # v1.17 : memorise la collection parcourue -> « film suivant » saura dans
    # quelle collection chercher si un de ses films est lance depuis ici
    if media_type == "boxset":
        boxset_match = re.search(r"[?&]ParentId=([0-9a-fA-F]+)", url)
        if boxset_match:
            HomeWindow().set_property("embycon_last_boxset_id", boxset_match.group(1))

    # v1.16 : contexte de tri (Films, Series, Collections, dans une
    # collection, dans une serie) -> tri serveur ou client selon les reglages.
    context = sort_context(media_type)
    sorted_explicitly = False
    client_sort_spec = None
    if default_sort != "none":
        library_sort = get_library_server_sort(settings, media_type)
        if library_sort is not None and not re.search(
            r"[?&]SortBy=", url, flags=re.IGNORECASE
        ):
            url += "&SortBy=" + library_sort[0] + "&SortOrder=" + library_sort[1]
            sorted_explicitly = True
            log.debug("Applied library server sort: {0}", library_sort)
        client_sort_spec = client_sort(settings.getSetting, context)
        if client_sort_spec is not None:
            sorted_explicitly = True

    # show a progress indicator if needed
    progress = None
    if settings.getSetting("showLoadProgress") == "true":
        progress = LoadingIndicator()
        progress.create(string_load(30112), string_load(30113))

    # update url for paging
    start_index_rex = "startindex=([0-9]{1,5})"
    limit_rex = "&limit=([0-9]{1,5})"
    limit_rex_p = "&Limit={ItemLimit}"
    start_index = 0
    page_limit = int(settings.getSetting("itemsPerPage"))
    # if the page_limit in the settings is not set but the url has a limit use the url limit number
    if page_limit == 0 and re.search(limit_rex, url, flags=re.IGNORECASE):
        url_limit_result = re.search(limit_rex, url, flags=re.IGNORECASE)
        if url_limit_result is not None:
            page_limit = int(url_limit_result.group(1))

    url_prev: str = ""
    url_next: str = ""
    if page_limit > 0 and media_type.lower() in ["movies", "movie", "tvshows"]:
        log.debug("Creating Paging URLS: {0}", url)

        # add StartIndex and Limit to the url if they are not there already
        # update limit to page limit if it is alreayd there
        if not re.search(start_index_rex, url, flags=re.IGNORECASE):
            url += "&StartIndex=0"

        if not re.search(limit_rex, url, flags=re.IGNORECASE) and not re.search(
            limit_rex_p, url, flags=re.IGNORECASE
        ):
            url += "&Limit=" + str(page_limit)
        else:
            url = re.sub(
                limit_rex, "&Limit=" + str(page_limit), url, flags=re.IGNORECASE
            )
            url = re.sub(
                limit_rex_p, "&Limit=" + str(page_limit), url, flags=re.IGNORECASE
            )

        # create NEXT and PREV urls
        start_index_match = re.search(start_index_rex, url, flags=re.IGNORECASE)
        start_index: int = 0
        if start_index_match is not None:
            start_index = int(start_index_match.group(1))
        if start_index > 0:
            prev_index = start_index - page_limit
            if prev_index < 0:
                prev_index = 0
            url_prev = re.sub(
                start_index_rex,
                "StartIndex=" + str(prev_index),
                url,
                flags=re.IGNORECASE,
            )
        url_next = re.sub(
            start_index_rex,
            "StartIndex=" + str(start_index + page_limit),
            url,
            flags=re.IGNORECASE,
        )

        log.debug("Paged URLS - url_current: {0}", url)
        log.debug("Paged URLS - url_prev: {0}", url_prev)
        log.debug("Paged URLS - url_next: {0}", url_next)

    # use the data manager to get the data
    # result = dataManager.get_content(url)

    # if this is a playlist then use the episode name format for the episodes
    if media_type == "playlist":
        params["name_format"] = "Episode|episode_name_format"

    # total_records = 0
    # if result is not None and isinstance(result, dict):
    #    total_records = result.get("TotalRecordCount", 0)

    use_cache = params.get("use_cache", "true") == "true"

    # EmbyCon FR: les listes qui filtrent les elements deja vus (IsPlayed=false,
    # ex. Ajouts recents / Dernieres quand hide_watched est actif) doivent rester
    # fraiches, sinon un episode fraichement vu reste visible tant que le cache
    # n'a pas expire. On desactive donc le cache pour ces listes volatiles.
    if re.search(r"IsPlayed=false", url, flags=re.IGNORECASE):
        use_cache = False

    result = None
    try:
        result = process_directory(url, progress, params, use_cache)
    except Exception as e:
        log.debug("There was an error processing the URL : {0}", e)
        data_manager = DataManager()
        log.debug("Clearing cache data of failed process_directory : {0}", url)
        data_manager.supprime_cache(url)
        raise

    if result is None:
        return 0

    dir_items = result.dir_items

    # EmbyCon FR: certains endpoints Emby (notamment /Items/Latest) ignorent le
    # filtre serveur IsPlayed=false. On retire donc les elements deja vus cote
    # client pour garantir qu'un episode/film deja lu ne reste pas dans une liste
    # "masquer les vus".
    if re.search(r"IsPlayed=false", url, flags=re.IGNORECASE):
        dir_items = [gi for gi in dir_items if gi.play_count == 0]

    # v1.16 : tri client (dans une serie : saisons / episodes)
    if client_sort_spec is not None:
        dir_items = sort_gui_items(dir_items, client_sort_spec[0], client_sort_spec[1])
        log.debug("Applied client sort: {0}", client_sort_spec)
        if context in ("BoxSets", "InBoxSet"):
            log.info("Tri {0} {1} : {2}", context, client_sort_spec, describe_order(dir_items))
        # v1.19.1 : liste de collections -> le tri du widget Arctic (date
        # d'ajout decroissante) suit l'ordre EmbyCon
        if context == "BoxSets":
            stamp_rank_dates(dir_items)

    # v1.16 : listes « recents » en ordre « plus ancien d'abord »
    if params.get("reverse") == "true":
        dir_items = list(reversed(dir_items))

    detected_type = result.detected_type
    total_records = result.total_records

    log.debug("total_records: {0}", total_records)

    # add paging items
    if page_limit > 0 and media_type.lower() in ["movies", "movie", "tvshows"]:
        if url_prev:
            list_item = xbmcgui.ListItem(
                "Prev Page ("
                + str(start_index - page_limit + 1)
                + "-"
                + str(start_index)
                + " of "
                + str(total_records)
                + ")"
            )
            u = (
                sys.argv[0]
                + "?url="
                + urllib.parse.quote(url_prev)
                + "&mode=GET_CONTENT&media_type=movies"
            )
            art = {
                "thumb": "http://localhost:24276/"
                + base64.b64encode(url_prev.encode("utf-8")).decode("utf-8")
            }
            list_item.setArt(art)
            log.debug("ADDING PREV ListItem: {0} - {1}", u, list_item)
            dir_items.insert(0, GuiItem(url=u, list_item=list_item, is_folder=True))

        if start_index + page_limit < total_records:
            upper_count = start_index + (page_limit * 2)
            if upper_count > total_records:
                upper_count = total_records
            list_item = xbmcgui.ListItem(
                "Next Page ("
                + str(start_index + page_limit + 1)
                + "-"
                + str(upper_count)
                + " of "
                + str(total_records)
                + ")"
            )
            u = (
                sys.argv[0]
                + "?url="
                + urllib.parse.quote(url_next)
                + "&mode=GET_CONTENT&media_type=movies"
            )
            art = {
                "thumb": "http://localhost:24276/"
                + base64.b64encode(url_next.encode("utf-8")).decode("utf-8")
            }
            list_item.setArt(art)
            log.debug("ADDING NEXT ListItem: {0} - {1}", u, list_item)
            dir_items.append(GuiItem(url=u, list_item=list_item, is_folder=True))

    # set the Kodi content type
    if content_type:
        xbmcplugin.setContent(pluginhandle, content_type)
    elif detected_type is not None:
        # if the media type is not set then try to use the detected type
        log.debug("Detected content type: {0}", detected_type)
        if detected_type == "Movie":
            view_type = "Movies"
            content_type = "movies"
        if detected_type == "Episode":
            view_type = "Episodes"
            content_type = "episodes"
        xbmcplugin.setContent(pluginhandle, content_type)

    # set the sort items
    if page_limit > 0 and media_type.lower() in ["movies", "movie", "tvshows"]:
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_UNSORTED)
    else:
        set_sort(pluginhandle, view_type, default_sort, sorted_explicitly)

    # Convert GuiItem objects to tuples for Kodi API
    dir_item_tuples = [item.as_tuple() for item in dir_items]
    xbmcplugin.addDirectoryItems(pluginhandle, dir_item_tuples)
    xbmcplugin.endOfDirectory(pluginhandle, cacheToDisc=False)

    # v1.16 : la vue memorisee n'est plus envoyee d'ici (trop tot : la liste
    # n'etait pas encore affichee et Kodi/le skin reimposaient leur vue). Le
    # moniteur de vues du service (view_memory.ViewMonitor) l'applique une
    # fois la liste chargee, par categorie.

    # send display items event
    # display_items_notification = {"view_type": view_type}
    # log.debug("Sending display_items with data {0}", display_items_notification)
    # send_event_notification("display_items", display_items_notification)

    if progress is not None:
        progress.update(100, string_load(30125))
        progress.close()

    return len(dir_items)


def get_library_server_sort(
    settings: xbmcaddon.Addon, media_type: str
) -> tuple[str, str] | None:
    """Traduit le reglage de tri d'un contexte en couple Emby (SortBy, SortOrder).

    v1.16 : delegue a sort_options. Le contenu d'une collection (boxset) a
    desormais son propre reglage (InBoxSet) au lieu d'heriter de celui de la
    liste des collections. None = ordre par defaut du serveur conserve.
    """
    return server_sort(settings.getSetting, sort_context(media_type))


def set_sort(
    pluginhandle: int, view_type: str, default_sort: str, sorted_explicitly: bool = False
) -> None:
    log.debug("SETTING_SORT for media type: {0}", view_type)

    # v1.16 : liste deja triee (serveur ou client) selon les reglages -> Kodi
    # doit afficher l'ordre recu ; la premiere methode ajoutee est la methode
    # active. Les autres restent disponibles dans le menu de tri du skin.
    if default_sort == "none" or sorted_explicitly:
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_UNSORTED)

    sorting_order_mapping = {
        "1": xbmcplugin.SORT_METHOD_UNSORTED,
        "2": xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE,
        "3": xbmcplugin.SORT_METHOD_VIDEO_YEAR,
        "4": xbmcplugin.SORT_METHOD_DATEADDED,
        "5": xbmcplugin.SORT_METHOD_GENRE,
        "6": xbmcplugin.SORT_METHOD_LABEL,
        "7": xbmcplugin.SORT_METHOD_VIDEO_RATING,
        "8": xbmcplugin.SORT_METHOD_EPISODE,
    }

    settings = xbmcaddon.Addon()
    preset_sort_order = ""
    if not sorted_explicitly:
        preset_sort_order = settings.getSetting("sort-" + view_type)
    log.debug("SETTING_SORT preset_sort_order: {0}", preset_sort_order)
    if preset_sort_order in sorting_order_mapping:
        xbmcplugin.addSortMethod(pluginhandle, sorting_order_mapping[preset_sort_order])

    if view_type == "BoxSets":
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(
            pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE
        )
    elif view_type == "Episodes":
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_EPISODE)
    elif view_type == "Music":
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_TRACKNUM)
    else:
        xbmcplugin.addSortMethod(
            pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE
        )
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_DATEADDED)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)


def stamp_rank_dates(dir_items: list) -> None:
    """Date d'ajout = rang dans l'ordre EmbyCon (voir sort_options.rank_stamps)."""
    for gui_item, stamp in zip(dir_items, rank_stamps(len(dir_items))):
        gui_item.sort_added = stamp
        try:
            gui_item.list_item.getVideoInfoTag().setDateAdded(stamp)
        except Exception as err:
            log.debug("stamp_rank_dates : {0}", err)


def _collections_ascending(settings: xbmcaddon.Addon, params: dict[str, str]) -> bool:
    """v1.19 : collections en ordre croissant -> date du premier film."""
    if params.get("type") == "recent_boxsets":
        return settings.getSetting("sort_order-RecentBoxSets") == "0"
    return settings.getSetting("sort_order-BoxSets") == "0"


@timer
def process_directory(
    url: str,
    progress: xbmcgui.DialogProgress | None,
    params: dict[str, str],
    use_cache_data: bool = False,
) -> DirectoryResult | None:
    log.debug("== ENTER: processDirectory ==")

    data_manager = DataManager()
    settings = xbmcaddon.Addon()
    download_utils = DownloadUtils()
    server = download_utils.get_server()
    if not server:
        xbmcgui.Dialog().ok(string_load(30135), string_load(30136))
        return None

    name_format = params.get("name_format", None)
    name_format_type = None
    if name_format is not None:
        name_format = urllib.parse.unquote(name_format)
        tokens = name_format.split("|")
        if len(tokens) == 2:
            name_format_type = tokens[0]
            name_format = settings.getSetting(tokens[1])
        else:
            name_format_type = None
            name_format = None

    max_image_width = int(settings.getSetting("max_image_width"))

    use_prem_date_for_added = settings.getSetting("use_prem_date_for_added") == "true"
    gui_options = GuiOptions(
        server=server,
        name_format=name_format,
        name_format_type=name_format_type,
        max_image_width=max_image_width,
        use_prem_date_for_added=use_prem_date_for_added,
    )

    use_cache = settings.getSetting("use_cache") == "true" and use_cache_data
    get_items_result = data_manager.get_items(url, gui_options, use_cache)
    item_list = get_items_result.item_list
    total_records = get_items_result.total_records
    cache_thread = get_items_result.cache_thread
    # flatten single season
    # if there is only one result and it is a season and you have flatten signle season turned on then
    # build a new url, set the content media type and call get content again
    flatten_tvshow_seasons = settings.getSetting("flatten_tvshow_seasons")
    if (
        flatten_tvshow_seasons == "1"
        and len(item_list) == 1
        and item_list[0].item_type == "Season"
    ):
        season_id = item_list[0].id
        series_id = item_list[0].series_id
        season_url = (
            "{server}/emby/Shows/" + series_id + "/Episodes"
            "?userId={userid}"
            + "&seasonId="
            + season_id
            + "&IsVirtualUnAired=false"
            + "&IsMissing=false"
            + "&Fields=SpecialEpisodeNumbers,{field_filters}"
            + "&format=json"
        )
        if progress is not None:
            progress.close()
        params["media_type"] = "Episodes"
        get_content(season_url, params)
        return None

    if (
        flatten_tvshow_seasons == "2"
        and len(item_list) > 0
        and item_list[0].item_type == "Season"
    ):
        season_id = item_list[0].id
        series_id = item_list[0].series_id
        season_url = (
            "{server}/emby/Shows/" + series_id + "/Episodes"
            "?userId={userid}" +
            #'&seasonId=' + season_id +
            "&IsVirtualUnAired=false"
            + "&IsMissing=false"
            + "&Fields=SpecialEpisodeNumbers,{field_filters}"
            + "&format=json"
        )
        if progress is not None:
            progress.close()
        params["media_type"] = "Episodes"
        get_content(season_url, params)
        return None

    hide_unwatched_details = settings.getSetting("hide_unwatched_details") == "true"

    # v1.18.4 : collections -> annee / date de sortie du film le plus recent
    # (Emby n'en donne souvent aucune : tri « date de sortie » ou « Annee »
    # sans effet dans les listes et les widgets)
    apply_collection_dates(item_list, _collections_ascending(settings, params))

    display_options = DisplayOptions()
    display_options.addCounts = settings.getSetting("addCounts") == "true"
    display_options.addResumePercent = settings.getSetting("addResumePercent") == "true"
    display_options.addSubtitleAvailable = (
        settings.getSetting("addSubtitleAvailable") == "true"
    )

    show_empty_folders = settings.getSetting("show_empty_folders") == "true"

    item_count = len(item_list)
    current_item = 1
    first_season_item = None
    total_unwatched = 0
    total_episodes = 0
    total_watched = 0

    detected_type: str | None = None
    dir_items: list[GuiItem] = []

    for item_details in item_list:
        item_details.total_items = item_count

        if progress is not None:
            percent_done = (float(current_item) / float(item_count)) * 100
            progress.update(int(percent_done), string_load(30126) + str(current_item))
            current_item = current_item + 1

        if detected_type is not None:
            if item_details.item_type != detected_type:
                detected_type = "mixed"
        else:
            detected_type = item_details.item_type

        if item_details.item_type == "Season" and first_season_item is None:
            log.debug("Setting First Season to : {0}", item_details.__dict__)
            first_season_item = item_details

        total_unwatched += item_details.unwatched_episodes
        total_episodes += item_details.total_episodes
        total_watched += item_details.watched_episodes

        # if set, for unwatched episodes dont show some of the info
        if (
            hide_unwatched_details
            and item_details.item_type == "Episode"
            and item_details.play_count == 0
        ):
            item_details.plot = "[Spoiler Alert]"
            item_details.art["poster"] = item_details.art["tvshow.poster"]
            item_details.art["thumb"] = item_details.art["tvshow.poster"]

        if item_details.item_type == "MusicArtist":
            u = "".join(
                [
                    "{server}/emby/Users/{userid}/items",
                    "?AlbumArtistIds=" + item_details.id,
                    "&IncludeItemTypes=MusicAlbum",
                    "&CollapseBoxSetItems=false",
                    "&Recursive=true",
                    "&format=json",
                ]
            )
            log.debug("TARGET URL = {0}", u)
            gui_item = add_gui_item(u, item_details, display_options)
            if gui_item:
                dir_items.append(gui_item)

        elif item_details.is_folder is True:
            if item_details.item_type == "Series":
                u = (
                    "{server}/emby/Shows/" + item_details.id + "/Seasons"
                    "?userId={userid}" + "&Fields={field_filters}" + "&format=json"
                )

            elif item_details.item_type == "Season":
                u = (
                    "{server}/emby/Shows/" + item_details.series_id + "/Episodes"
                    "?userId={userid}"
                    + "&seasonId="
                    + item_details.id
                    + "&IsVirtualUnAired=false"
                    + "&IsMissing=false"
                    + "&Fields=SpecialEpisodeNumbers,{field_filters}"
                    + "&format=json"
                )

            else:
                u = "".join(
                    [
                        "{server}/emby/Users/{userid}/items",
                        "?ParentId=" + item_details.id,
                        "&IsVirtualUnAired=false",
                        "&IsMissing=false",
                        "&Fields={field_filters}",
                        "&format=json",
                    ]
                )

            default_sort = item_details.item_type == "Playlist"

            if show_empty_folders or item_details.recursive_item_count != 0:
                gui_item = add_gui_item(
                    u, item_details, display_options, default_sort=default_sort
                )
                if gui_item:
                    dir_items.append(gui_item)
            else:
                log.debug("Dropping empty folder item : {0}", item_details.__dict__)

        else:
            u = item_details.id
            gui_item = add_gui_item(u, item_details, display_options, folder=False)
            if gui_item:
                dir_items.append(gui_item)

    # add the all episodes item
    show_all_episodes = settings.getSetting("show_all_episodes") == "true"
    if (
        show_all_episodes
        and first_season_item is not None
        and len(dir_items) > 1
        and first_season_item.series_id is not None
    ):
        series_url = (
            "{server}/emby/Shows/" + first_season_item.series_id + "/Episodes"
            "?userId={userid}" +
            # '&seasonId=' + season_id +
            "&IsVirtualUnAired=false"
            + "&IsMissing=false"
            + "&Fields=SpecialEpisodeNumbers,{field_filters}"
            + "&format=json"
        )
        played = 0
        overlay = "7"
        if total_unwatched == 0:
            played = 1
            overlay = "6"

        item_details = ItemDetails()

        item_details.id = first_season_item.id
        item_details.name = string_load(30290)
        item_details.art = first_season_item.art
        item_details.play_count = played
        item_details.overlay = overlay
        item_details.name_format = "Episode|episode_name_format"
        item_details.series_name = first_season_item.series_name
        item_details.item_type = "Season"
        item_details.unwatched_episodes = total_unwatched
        item_details.total_episodes = total_episodes
        item_details.watched_episodes = total_watched
        item_details.mode = "GET_CONTENT"

        gui_item = add_gui_item(series_url, item_details, display_options, folder=True)
        if gui_item:
            # v1.16 : pseudo-element, toujours en fin de liste quel que soit le tri
            gui_item.sort_date = ""
            gui_item.sort_name = ""
            dir_items.append(gui_item)

    if cache_thread is not None:
        cache_thread.start()

    return DirectoryResult(
        dir_items=dir_items, detected_type=detected_type, total_records=total_records
    )
