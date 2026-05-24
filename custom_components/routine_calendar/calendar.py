"""Calendar platform: one entity listing all routines as events."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CALENDAR_ENTITY_UNIQUE_ID_SUFFIX,
    CONF_DUE_DATE,
    CONF_ID,
    CONF_NAME,
    DOMAIN,
    SIGNAL_ROUTINES_CHANGED,
)
from .coordinator import RoutineCalendarCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoutineCalendarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RoutineCalendarEntity(coordinator, entry)])


class RoutineCalendarEntity(CalendarEntity):
    """A single calendar entity that aggregates all routine due dates."""

    _attr_has_entity_name = False
    _attr_supported_features = CalendarEntityFeature(0)

    def __init__(self, coordinator: RoutineCalendarCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_name = entry.title
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{CALENDAR_ENTITY_UNIQUE_ID_SUFFIX}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ROUTINES_CHANGED, self._handle_change
            )
        )

    @callback
    def _handle_change(self) -> None:
        self.async_write_ha_state()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming routine event."""
        today = dt_util.now().date()
        upcoming = sorted(
            (r for r in self._coordinator.routines if r[CONF_DUE_DATE] >= today),
            key=lambda r: r[CONF_DUE_DATE],
        )
        if not upcoming:
            return None
        return _routine_to_event(upcoming[0])

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date
        return [
            _routine_to_event(r)
            for r in self._coordinator.routines
            if start <= r[CONF_DUE_DATE] < end
        ]


def _routine_to_event(routine: dict) -> CalendarEvent:
    due: date = routine[CONF_DUE_DATE]
    return CalendarEvent(
        start=due,
        end=due + timedelta(days=1),
        summary=routine[CONF_NAME],
        uid=routine[CONF_ID],
    )
