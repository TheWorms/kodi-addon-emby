# -*- coding: utf-8 -*-

#################################################################################################
from __future__ import annotations

import json
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui

from .functions import play_action
from .simple_logging import SimpleLogging
from . import clientinfo
from . import downloadutils
from .jsonrpc import JsonRpc
from .kodi_utils import HomeWindow
from .websocket import WebSocketApp
from .library_change_monitor import LibraryChangeMonitor

log = SimpleLogging(__name__)


class WebSocketClient(threading.Thread):
    _shared_state = {}

    _client = None
    _stop_websocket: bool = False
    _library_monitor: LibraryChangeMonitor | None = None

    def __init__(self, library_change_monitor: LibraryChangeMonitor) -> None:
        self.__dict__ = self._shared_state
        self.monitor = xbmc.Monitor()

        self.client_info = clientinfo.ClientInformation()
        self.device_id = self.client_info.get_device_id()

        self._library_monitor = library_change_monitor

        threading.Thread.__init__(self)

    def on_message(self, message: str) -> None:
        result = json.loads(message)
        message_type = result["MessageType"]

        if message_type == "Play":
            data = result["Data"]
            self._play(data)

        elif message_type == "Playstate":
            data = result["Data"]
            self._playstate(data)

        elif message_type == "UserDataChanged":
            data = result["Data"]
            self._library_changed(data)

        elif message_type == "LibraryChanged":
            data = result["Data"]
            self._library_changed(data)

        elif message_type == "GeneralCommand":
            data = result["Data"]
            self._general_commands(data)

        else:
            log.debug("WebSocket Message Type: {0}", message)

    def _library_changed(self, data: dict) -> None:
        log.debug("Library_Changed: {0}", data)
        if self._library_monitor is not None:
            self._library_monitor.check_for_updates()

    def _play(self, data: dict) -> None:
        item_ids = data["ItemIds"]
        command = data["PlayCommand"]

        if command == "PlayNow":
            home_screen = HomeWindow()
            home_screen.set_property("skip_select_user", "true")

            startat = data.get("StartPositionTicks", -1)
            log.debug("WebSocket Message PlayNow: {0}", data)

            media_source_id = data.get("MediaSourceId", "")
            subtitle_stream_index = data.get("SubtitleStreamIndex", None)
            audio_stream_index = data.get("AudioStreamIndex", None)

            start_index = data.get("StartIndex", 0)

            if start_index > 0 and start_index < len(item_ids):
                item_ids = item_ids[start_index:]

            if len(item_ids) == 1:
                item_ids = item_ids[0]

            params = {}
            params["item_id"] = item_ids
            params["auto_resume"] = str(startat)
            params["media_source_id"] = media_source_id
            params["subtitle_stream_index"] = subtitle_stream_index
            params["audio_stream_index"] = audio_stream_index
            play_action(params)

    def _playstate(self, data: dict) -> None:
        command = data["Command"]
        player = xbmc.Player()

        actions = {
            "Stop": player.stop,
            "Unpause": player.pause,
            "Pause": player.pause,
            "PlayPause": player.pause,
            "NextTrack": player.playnext,
            "PreviousTrack": player.playprevious,
        }
        if command == "Seek":
            if player.isPlaying():
                seek_to = data["SeekPositionTicks"]
                seek_time = seek_to / 10000000.0
                player.seekTime(seek_time)
                log.debug("Seek to {0}", seek_time)

        elif command in actions:
            actions[command]()
            log.debug("Command: {0} completed", command)

        else:
            log.debug("Unknown command: {0}", command)
            return

    def _general_commands(self, data: dict) -> None:
        command = data["Name"]
        arguments = data["Arguments"]

        if command in (
            "Mute",
            "Unmute",
            "SetVolume",
            "SetSubtitleStreamIndex",
            "SetAudioStreamIndex",
            "SetRepeatMode",
        ):
            player = xbmc.Player()
            # These commands need to be reported back
            if command == "Mute":
                xbmc.executebuiltin("Mute")

            elif command == "Unmute":
                xbmc.executebuiltin("Mute")

            elif command == "SetVolume":
                # v1.14.1 (audit S5) : la valeur vient du serveur — ne pas
                # l'injecter telle quelle dans une commande Kodi
                try:
                    volume = max(0, min(100, int(arguments["Volume"])))
                except (KeyError, TypeError, ValueError):
                    log.error(
                        "SetVolume websocket invalide : {0}", arguments.get("Volume")
                    )
                else:
                    xbmc.executebuiltin("SetVolume(%s[,showvolumebar])" % volume)

            elif command == "SetAudioStreamIndex":
                index = int(arguments["Index"])
                player.setAudioStream(index - 1)

            elif command == "SetSubtitleStreamIndex":
                index = int(arguments["Index"])
                player.setSubtitleStream(index - 1)

            elif command == "SetRepeatMode":
                # v1.14.1 (audit S5) : liste blanche — la valeur vient du
                # serveur ; RepeatNone n'est pas une commande Kodi, son
                # equivalent est RepeatOff
                mode = {
                    "RepeatNone": "RepeatOff",
                    "RepeatAll": "RepeatAll",
                    "RepeatOne": "RepeatOne",
                }.get(arguments.get("RepeatMode"))
                if mode is not None:
                    xbmc.executebuiltin("PlayerControl(%s)" % mode)

        elif command == "DisplayMessage":
            # header = arguments['Header']
            text = arguments["Text"]
            # show notification here
            log.debug("WebSocket DisplayMessage: {0}", text)
            xbmcgui.Dialog().notification("EmbyCon", text)

        elif command == "SendString":
            params = {"text": arguments["String"], "done": False}
            JsonRpc("Input.SendText").execute(params)

        elif command in ("MoveUp", "MoveDown", "MoveRight", "MoveLeft"):
            # Commands that should wake up display
            actions = {
                "MoveUp": "Input.Up",
                "MoveDown": "Input.Down",
                "MoveRight": "Input.Right",
                "MoveLeft": "Input.Left",
            }
            JsonRpc(actions[command]).execute({})

        elif command == "GoHome":
            JsonRpc("GUI.ActivateWindow").execute({"window": "home"})

        elif command == "Guide":
            JsonRpc("GUI.ActivateWindow").execute({"window": "tvguide"})

        else:
            builtin = {
                "ToggleFullscreen": "Action(FullScreen)",
                "ToggleOsdMenu": "Action(OSD)",
                "ToggleContextMenu": "Action(ContextMenu)",
                "Select": "Action(Select)",
                "Back": "Action(back)",
                "PageUp": "Action(PageUp)",
                "NextLetter": "Action(NextLetter)",
                "GoToSearch": "VideoLibrary.Search",
                "GoToSettings": "ActivateWindow(Settings)",
                "PageDown": "Action(PageDown)",
                "PreviousLetter": "Action(PrevLetter)",
                "TakeScreenshot": "TakeScreenshot",
                "ToggleMute": "Mute",
                "VolumeUp": "Action(VolumeUp)",
                "VolumeDown": "Action(VolumeDown)",
            }
            if command in builtin:
                xbmc.executebuiltin(builtin[command])

    def on_close(self) -> None:
        log.debug("Closed")

    def on_open(self) -> None:
        log.debug("Connected")
        self.post_capabilities()

    def on_error(self, error: Exception) -> None:
        log.error("Error: {0}", error)

    def run(self) -> None:
        # v1.14 : rearmement du drapeau d'arret au demarrage du thread.
        # Sans ceci, un client reconstruit apres un stop heriterait du
        # drapeau True et mourrait a la premiere deconnexion. Sans risque de
        # zombie : service.py joint l'ancien thread avant de relancer.
        self._stop_websocket = False

        # websocket.enableTrace(True)
        download_utils = downloadutils.DownloadUtils()

        token = None
        auth_attempts = 0
        auth_retry_delay = 10
        while token is None or token == "":
            auth_attempts += 1
            download_utils.set_host_domain()
            token = download_utils.authenticate()
            if token is None or token == "":
                if auth_attempts >= 6:
                    log.error("WebSocketClient: auth failed after {0} attempts, giving up", auth_attempts)
                    return
                log.debug("WebSocketClient: auth attempt {0} failed, retrying in {1}s", auth_attempts, auth_retry_delay)
                if self.monitor.waitForAbort(auth_retry_delay):
                    return
                auth_retry_delay = min(auth_retry_delay * 2, 60)

        # Get the appropriate prefix for the websocket
        download_utils.set_host_domain()
        server = download_utils.get_server()
        if server is None:
            log.error("No server found for WebSocketClient")
            return

        if "https" in server:
            server = server.replace("https", "wss")
        else:
            server = server.replace("http", "ws")

        websocket_url = "%s/embywebsocket?api_key=%s&deviceId=%s" % (
            server,
            token,
            self.device_id,
        )
        log.debug("websocket url: {0}/embywebsocket?api_key=****&deviceId={1}", server, self.device_id)

        self._client = WebSocketApp(
            websocket_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        log.debug("Starting WebSocketClient")

        # v1.14 phase 2c : heartbeat reglable via le reglage websocket_ping_interval
        # (defaut 20 s, plancher 5 s) au lieu des 10 s codes en dur
        try:
            ping_interval = int(xbmcaddon.Addon().getSetting("websocket_ping_interval"))
        except (TypeError, ValueError):
            ping_interval = 20
        if ping_interval < 5:
            ping_interval = 5

        # v1.14 phase 2c : backoff exponentiel 1 -> 2 -> 4 s ... plafonne a 60 s,
        # remis a 1 apres 5 minutes de connexion stable
        delai_reconnexion = 1
        while not self.monitor.abortRequested():
            # v1.14 : ne pas ouvrir de connexion si un arret a deja ete demande
            if self._stop_websocket:
                break

            debut_connexion = time.monotonic()
            self._client.run_forever(ping_interval=ping_interval)

            if self._stop_websocket:
                break

            # connexion tenue au moins 5 min : plus courte attente a la reprise
            if time.monotonic() - debut_connexion >= 300:
                delai_reconnexion = 1
                log.debug("Connexion websocket stable, delai de reconnexion remis a 1s")

            # v1.14 : backoff decoupe en pas de 1 s - un arret demande pendant
            # l'attente est vu en 1 s (fini la reconnexion fantome apres stop)
            log.debug("Reconnexion websocket dans {0}s", delai_reconnexion)
            reste = delai_reconnexion
            while reste > 0:
                if self.monitor.waitForAbort(1):
                    log.debug("WebSocketClient Stopped")
                    return
                if self._stop_websocket:
                    break
                reste -= 1

            if self._stop_websocket:
                log.debug("Arret demande pendant le backoff, pas de reconnexion")
                break

            delai_reconnexion = min(delai_reconnexion * 2, 60)
            log.debug("Reconnecting WebSocket")

        log.debug("WebSocketClient Stopped")

    def stop_client(self) -> None:
        self._stop_websocket = True
        if self._client is not None:
            self._client.close()
        log.debug("Stopping WebSocket (stop_client called)")

    def post_capabilities(self) -> None:
        download_utils = downloadutils.DownloadUtils()
        download_utils.post_capabilities()
