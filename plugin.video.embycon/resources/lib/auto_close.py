# Gnu General Public License - see LICENSE.TXT
from __future__ import annotations

import time
import threading
from typing import TYPE_CHECKING

import xbmc
import xbmcgui

from .simple_logging import SimpleLogging

if TYPE_CHECKING:
    from .playnext import PlayNextDialog


log = SimpleLogging(__name__)


class ActionAutoClose(threading.Thread):
    last_interaction = time.time()
    parent_dialog: xbmcgui.WindowXMLDialog | None = None
    stop_thread = False
    progress_call_back: PlayNextDialog | None = None
    time_out = 20

    def __init__(self, parent: xbmcgui.WindowXMLDialog) -> None:
        self.parent_dialog = parent
        self.stop_thread = False
        self.last_interaction = time.time()
        threading.Thread.__init__(self)
        self.time_out = 20

    def run(self) -> None:
        log.debug("ActionAutoClose Running")
        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and not self.stop_thread:
            time_since_last = time.time() - self.last_interaction
            log.debug("ActionAutoClose time_since_last : {0}", time_since_last)

            if time_since_last > self.time_out:
                log.debug("ActionAutoClose Closing Parent")
                # EmbyCon FR: le dialogue parent peut etre ferme/detruit par un
                # autre thread entre deux iterations -> ne jamais planter Kodi
                # sur un objet GUI disparu (use-after-free, segfault
                # CGUIControlLookup::RemoveLookup).
                if self.parent_dialog is not None and not self.stop_thread:
                    try:
                        self.parent_dialog.close()
                    except Exception:
                        pass
                break

            if self.progress_call_back is not None and not self.stop_thread:
                percentage = (float(time_since_last) / float(self.time_out)) * 100
                try:
                    self.progress_call_back.update_progress(percentage)
                except Exception:
                    # dialogue detruit pendant l'appel -> sortie propre
                    break

            monitor.waitForAbort(0.1)

        log.debug("ActionAutoClose Exited")

    def set_timeout(self, t: int) -> None:
        self.time_out = t

    def set_callback(self, call_back: PlayNextDialog) -> None:
        self.progress_call_back = call_back

    def set_last(self) -> None:
        self.last_interaction = time.time()
        log.debug("ActionAutoClose set_last : {0}", self.last_interaction)

    def stop(self) -> None:
        log.debug("ActionAutoClose stop_thread called")
        self.stop_thread = True
