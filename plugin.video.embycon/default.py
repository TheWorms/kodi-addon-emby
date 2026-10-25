# Gnu General Public License - see LICENSE.TXT

from resources.lib.simple_logging import SimpleLogging
from resources.lib.functions import main_entry_point
from resources.lib.settings_migration import migrate_settings

log = SimpleLogging("default")

# v1.20.0 : nouvelle organisation des reglages (conversion unique)
migrate_settings()

log.debug("About to enter mainEntryPoint()")

main_entry_point()

# clear done and exit.
# sys.modules.clear()
