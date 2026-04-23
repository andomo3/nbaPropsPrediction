"""
Timezone helpers.

The Railway server runs in UTC, but the NBA schedule (and ESPN's scoreboard
`dates=YYYYMMDD` parameter) is keyed to US Eastern Time. Using UTC
`date.today()` causes day-rollover bugs: after 8 PM ET (= midnight UTC), the
server thinks it is "tomorrow" while the games are still happening tonight.

Always use `et_today()` for any user-facing "today" that maps to the NBA
schedule.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

NBA_TZ = ZoneInfo("America/New_York")


def et_today() -> date:
    """Return the current date in US Eastern Time (NBA scheduling timezone)."""
    return datetime.now(NBA_TZ).date()
