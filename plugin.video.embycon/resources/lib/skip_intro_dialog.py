# Gnu General Public License - see LICENSE.TXT
from __future__ import annotations

import xbmc
import xbmcgui
import xbmcaddon

import threading

from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)


class SkipIntroMonitor(threading.Thread):
    intro_start_ticks: int = 0
    intro_end_ticks: int = 0
    auto_skip: bool = False
    original_play_path: str | None = None

    def __init__(self) -> None:
        threading.Thread.__init__(self)

    def run(self) -> None:
        log.debug("SkipIntroMonitor Running")

        settings = xbmcaddon.Addon()
        addon_path = settings.getAddonInfo("path")
        skip_intro_dialog = None

        intro_start_sec = (self.intro_start_ticks / 1000) / 10000
        intro_end_sec = (self.intro_end_ticks / 1000) / 10000

        player = xbmc.Player()
        monitor = xbmc.Monitor()
        while not monitor.abortRequested():
            play_time = player.getTime()
            play_path = player.getPlayingFile()

            if play_path != self.original_play_path:
                log.debug(
                    "SkipIntroMonitor original file no longer playing: {0} {1}",
                    play_path,
                    self.original_play_path,
                )
                break

            if skip_intro_dialog is None and (
                intro_start_sec < play_time < intro_end_sec
            ):
                log.debug(
                    "SkipIntroMonitor doing skip intro action: {0} {1} {2}",
                    intro_start_sec,
                    play_time,
                    intro_end_sec,
                )
                if self.auto_skip:
                    log.debug("SkipIntroMonitor auto skip")
                    player.seekTime(intro_end_sec)
                else:
                    log.debug("SkipIntroMonitor show dialog")
                    skip_intro_dialog = SkipIntroDialog(
                        "SkipIntroDialog.xml", addon_path, "default", "720p"
                    )
                    skip_intro_dialog.show()

            # player skipped past intro end so exit the monitor
            if play_time > intro_end_sec:
                log.debug(
                    "SkipIntroMonitor player position past intro end time: {0} {1}",
                    play_time,
                    intro_end_sec,
                )
                if skip_intro_dialog is not None:
                    skip_intro_dialog.close()
                break

            # dialog has been actioned so do the thing
            if skip_intro_dialog is not None and not skip_intro_dialog.dialog_open:
                log.debug(
                    "SkipIntroMonitor skip intro dialog result: {0}",
                    skip_intro_dialog.confirm,
                )
                if skip_intro_dialog.confirm:
                    player.seekTime(intro_end_sec)
                break

            monitor.waitForAbort(1.0)

        log.debug("SkipIntroMonitor Exited")

    def set_times(self, start: int, end: int) -> None:
        self.intro_start_ticks = start
        self.intro_end_ticks = end

    def set_auto_skip(self, auto_skip: bool) -> None:
        self.auto_skip = auto_skip

    def set_play_path(self, path: str) -> None:
        self.original_play_path = path


class SkipIntroDialog(xbmcgui.WindowXMLDialog):
    dialog_open = False
    confirm = False
    action_exitkeys_id = None

    def __init__(
        self,
        xmlFilename: str,
        scriptPath: str,
        defaultSkin: str = "default",
        defaultRes: str = "720p",
    ) -> None:
        log.debug("SkipIntroPromptDialog: __init__")
        xbmcgui.WindowXML.__init__(
            self, xmlFilename, scriptPath, defaultSkin, defaultRes
        )
        self.dialog_open = True

    def onInit(self) -> None:
        log.debug("SkipIntroPromptDialog: onInit")
        self.action_exitkeys_id = [10, 13]

    def onFocus(self, controlId: int) -> None:
        pass

    def onAction(self, action: xbmcgui.Action) -> None:
        if action.getId() == 10:  # ACTION_PREVIOUS_MENU
            self.dialog_open = False
            self.close()
        elif action.getId() == 92:  # ACTION_NAV_BACK
            self.dialog_open = False
            self.close()
        else:
            log.debug("SkipIntroPromptDialog: onAction: {0}", action.getId())

    def onClick(self, controlId: int) -> None:
        if controlId == 1:
            self.confirm = True
            self.dialog_open = False
            self.close()


class SkipCreditsMonitor(threading.Thread):
    """Surveille la lecture pour proposer/effectuer le saut du generique de fin.

    Declenche au marqueur Emby CreditsStart : soit affiche un bouton
    (mode 1), soit saute directement vers la fin (mode 2), ce qui enchaine
    sur l'episode suivant si la lecture auto est active.
    """

    credits_start_ticks: int = 0
    before_end_sec: float = 0
    auto_skip: bool = False
    original_play_path: str | None = None

    def __init__(self) -> None:
        threading.Thread.__init__(self)

    def run(self) -> None:
        log.debug("SkipCreditsMonitor Running")

        settings = xbmcaddon.Addon()
        addon_path = settings.getAddonInfo("path")
        credits_dialog = None

        credits_start_sec = (self.credits_start_ticks / 1000) / 10000

        player = xbmc.Player()
        monitor = xbmc.Monitor()
        while not monitor.abortRequested():
            try:
                play_time = player.getTime()
                play_path = player.getPlayingFile()
                total_time = player.getTotalTime()
            except Exception:
                break

            if play_path != self.original_play_path:
                log.debug("SkipCreditsMonitor original file no longer playing")
                break

            # Repli : declencher X secondes avant la fin quand le serveur
            # n'a pas de marqueur CreditsStart (credits_start_sec vaut 0)
            if (
                credits_start_sec <= 0
                and self.before_end_sec > 0
                and total_time > 0
            ):
                credits_start_sec = total_time - self.before_end_sec

            # Tres proche de la fin : plus rien a faire
            if total_time > 0 and play_time >= (total_time - 2):
                if credits_dialog is not None:
                    credits_dialog.close()
                break

            if (
                credits_dialog is None
                and credits_start_sec > 0
                and play_time >= credits_start_sec
            ):
                log.debug("SkipCreditsMonitor trigger at {0}", play_time)
                if self.auto_skip:
                    self._skip_to_end(player, total_time)
                    break
                else:
                    credits_dialog = SkipIntroDialog(
                        "SkipCreditsDialog.xml", addon_path, "default", "720p"
                    )
                    credits_dialog.show()

            if credits_dialog is not None and not credits_dialog.dialog_open:
                log.debug(
                    "SkipCreditsMonitor dialog result: {0}", credits_dialog.confirm
                )
                if credits_dialog.confirm:
                    self._skip_to_end(player, total_time)
                break

            monitor.waitForAbort(1.0)

        log.debug("SkipCreditsMonitor Exited")

    def _skip_to_end(self, player: xbmc.Player, total_time: float) -> None:
        try:
            if total_time <= 0:
                total_time = player.getTotalTime()
            if total_time > 3:
                player.seekTime(total_time - 1)
        except Exception as e:
            log.error("SkipCreditsMonitor skip failed: {0}", e)

    def set_credits_start(self, start: int) -> None:
        self.credits_start_ticks = start

    def set_before_end(self, seconds: float) -> None:
        self.before_end_sec = seconds

    def set_auto_skip(self, auto_skip: bool) -> None:
        self.auto_skip = auto_skip

    def set_play_path(self, path: str) -> None:
        self.original_play_path = path
