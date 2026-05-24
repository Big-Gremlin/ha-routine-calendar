"""Constants for the Routine Calendar integration."""
from __future__ import annotations

DOMAIN = "routine_calendar"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.routines"

# Config / options keys
CONF_ROUTINES = "routines"
CONF_NAME = "name"
CONF_DUE_DATE = "due_date"
CONF_INTERVAL_VALUE = "interval_value"
CONF_INTERVAL_UNIT = "interval_unit"
CONF_LAST_COMPLETED = "last_completed"
CONF_ID = "id"
CONF_ICON = "icon"

# Interval units
UNIT_DAYS = "days"
UNIT_WEEKS = "weeks"
UNIT_MONTHS = "months"
UNIT_YEARS = "years"
INTERVAL_UNITS = [UNIT_DAYS, UNIT_WEEKS, UNIT_MONTHS, UNIT_YEARS]

# Services
SERVICE_COMPLETE = "complete"

# Service / call attributes
ATTR_ROUTINE_ID = "routine_id"
ATTR_COMPLETED_ON = "completed_on"

# Signals
SIGNAL_ROUTINES_CHANGED = f"{DOMAIN}_routines_changed"

# Calendar entity unique-id suffix (combined with entry_id at runtime)
CALENDAR_ENTITY_UNIQUE_ID_SUFFIX = "calendar"

SAVE_DELAY_SECONDS = 2
