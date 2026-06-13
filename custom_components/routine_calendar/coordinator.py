"""Coordinator: routine storage, completion logic, service registration."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_COMPLETED_ON,
    ATTR_ROUTINE_ID,
    CONF_DUE_DATE,
    CONF_ICON,
    CONF_ID,
    CONF_INTERVAL_UNIT,
    CONF_INTERVAL_VALUE,
    CONF_LAST_COMPLETED,
    CONF_NAME,
    CONF_ROUTINES,
    DOMAIN,
    INTERVAL_UNITS,
    SAVE_DELAY_SECONDS,
    SERVICE_COMPLETE,
    SIGNAL_ROUTINES_CHANGED,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .recurrence import add_interval

_LOGGER = logging.getLogger(__name__)
_UNSET: Any = object()


def _parse_date(value: Any) -> date:
    """Accept date or ISO string, return date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


class RoutineCalendarCoordinator:
    """Holds routines, persists them, owns the completion logic."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        # routine_id -> routine dict
        self._routines: dict[str, dict[str, Any]] = {}
        self._unsub_listeners: list = []

    # ------------------------------------------------------------------ API

    @property
    def routines(self) -> list[dict[str, Any]]:
        """All routines as a list, sorted by due_date."""
        return sorted(self._routines.values(), key=lambda r: r[CONF_DUE_DATE])

    def get(self, routine_id: str) -> dict[str, Any] | None:
        return self._routines.get(routine_id)

    async def async_initialize(self) -> None:
        """Load persisted state."""
        data = await self._store.async_load() or {}
        for raw in data.get(CONF_ROUTINES) or []:
            try:
                rid = raw[CONF_ID]
                self._routines[rid] = {
                    CONF_ID: rid,
                    CONF_NAME: raw[CONF_NAME],
                    CONF_DUE_DATE: _parse_date(raw[CONF_DUE_DATE]),
                    CONF_INTERVAL_VALUE: int(raw[CONF_INTERVAL_VALUE]),
                    CONF_INTERVAL_UNIT: raw[CONF_INTERVAL_UNIT],
                    CONF_LAST_COMPLETED: (
                        _parse_date(raw[CONF_LAST_COMPLETED])
                        if raw.get(CONF_LAST_COMPLETED)
                        else None
                    ),
                    CONF_ICON: raw.get(CONF_ICON),
                }
            except (KeyError, ValueError):
                _LOGGER.exception("Skipping malformed stored routine: %s", raw)

        self._unsub_listeners.append(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
            )
        )

    async def async_shutdown(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        await self._store.async_save(self._serialize())

    # ----------------------------------------------------------- mutations

    async def async_add_routine(
        self,
        name: str,
        due_date: date,
        interval_value: int,
        interval_unit: str,
        icon: str | None = None,
    ) -> str:
        """Create a new routine and return its id."""
        _validate_unit(interval_unit)
        _validate_value(interval_value)
        rid = uuid.uuid4().hex
        self._routines[rid] = {
            CONF_ID: rid,
            CONF_NAME: name,
            CONF_DUE_DATE: due_date,
            CONF_INTERVAL_VALUE: int(interval_value),
            CONF_INTERVAL_UNIT: interval_unit,
            CONF_LAST_COMPLETED: None,
            CONF_ICON: icon or None,
        }
        await self._async_save_and_notify()
        return rid

    async def async_update_routine(
        self,
        routine_id: str,
        *,
        name: str | None = None,
        due_date: date | None = None,
        interval_value: int | None = None,
        interval_unit: str | None = None,
        icon: Any = _UNSET,
    ) -> None:
        """Update one or more fields of a routine."""
        routine = self._routines.get(routine_id)
        if routine is None:
            raise KeyError(routine_id)
        if name is not None:
            routine[CONF_NAME] = name
        if due_date is not None:
            routine[CONF_DUE_DATE] = due_date
        if interval_value is not None:
            _validate_value(interval_value)
            routine[CONF_INTERVAL_VALUE] = int(interval_value)
        if interval_unit is not None:
            _validate_unit(interval_unit)
            routine[CONF_INTERVAL_UNIT] = interval_unit
        if icon is not _UNSET:
            routine[CONF_ICON] = icon or None
        await self._async_save_and_notify()

    async def async_remove_routine(self, routine_id: str) -> None:
        if self._routines.pop(routine_id, None) is not None:
            self._cleanup_routine_registries(routine_id)
            await self._async_save_and_notify()

    @callback
    def _cleanup_routine_registries(self, routine_id: str) -> None:
        """Remove entity and device registry entries for a deleted routine.

        Disabled entities never receive SIGNAL_ROUTINES_CHANGED and cannot
        clean themselves up, so the coordinator must do it centrally.
        """
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)
        device = device_reg.async_get_device(identifiers={(DOMAIN, routine_id)})
        if device is None:
            return
        for entry in er.async_entries_for_device(
            entity_reg, device.id, include_disabled_entities=True
        ):
            entity_reg.async_remove(entry.entity_id)
        device_reg.async_remove_device(device.id)

    async def async_complete(
        self, routine_id: str, completed_on: date | None = None
    ) -> None:
        """Mark routine as completed and reschedule next due date."""
        routine = self._routines.get(routine_id)
        if routine is None:
            raise KeyError(routine_id)
        completed_on = completed_on or dt_util.now().date()
        await self.async_set_last_completed(routine_id, completed_on)

    async def async_set_last_completed(
        self, routine_id: str, completed_on: date
    ) -> None:
        """Set the last-completed date and recompute the next due date."""
        routine = self._routines.get(routine_id)
        if routine is None:
            raise KeyError(routine_id)
        routine[CONF_LAST_COMPLETED] = completed_on
        routine[CONF_DUE_DATE] = add_interval(
            completed_on,
            routine[CONF_INTERVAL_VALUE],
            routine[CONF_INTERVAL_UNIT],
        )
        await self._async_save_and_notify()

    # ------------------------------------------------------------ helpers

    def _serialize(self) -> dict[str, Any]:
        return {
            CONF_ROUTINES: [
                {
                    CONF_ID: r[CONF_ID],
                    CONF_NAME: r[CONF_NAME],
                    CONF_DUE_DATE: r[CONF_DUE_DATE].isoformat(),
                    CONF_INTERVAL_VALUE: r[CONF_INTERVAL_VALUE],
                    CONF_INTERVAL_UNIT: r[CONF_INTERVAL_UNIT],
                    CONF_LAST_COMPLETED: (
                        r[CONF_LAST_COMPLETED].isoformat()
                        if r[CONF_LAST_COMPLETED]
                        else None
                    ),
                    CONF_ICON: r.get(CONF_ICON),
                }
                for r in self._routines.values()
            ]
        }

    async def _async_save_and_notify(self) -> None:
        self._store.async_delay_save(self._serialize, SAVE_DELAY_SECONDS)
        async_dispatcher_send(self.hass, SIGNAL_ROUTINES_CHANGED)

    async def _async_handle_stop(self, _event: Event) -> None:
        await self._store.async_save(self._serialize())


def _validate_unit(unit: str) -> None:
    if unit not in INTERVAL_UNITS:
        raise vol.Invalid(f"unknown interval unit: {unit}")


def _validate_value(value: int) -> None:
    if int(value) <= 0:
        raise vol.Invalid(f"interval value must be positive, got {value}")


# ----------------------------------------------------------- service registration


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_COMPLETE):
        return

    async def _handle_complete(call: ServiceCall) -> None:
        routine_id = call.data.get(ATTR_ROUTINE_ID)
        completed_on_raw = call.data.get(ATTR_COMPLETED_ON)
        completed_on = _parse_date(completed_on_raw) if completed_on_raw else None
        if not routine_id:
            return
        for coordinator in list(hass.data.get(DOMAIN, {}).values()):
            if coordinator.get(routine_id) is not None:
                await coordinator.async_complete(routine_id, completed_on)
                return
        _LOGGER.warning("No routine with id %s found", routine_id)

    schema = vol.Schema(
        {
            vol.Required(ATTR_ROUTINE_ID): str,
            vol.Optional(ATTR_COMPLETED_ON): str,
        }
    )

    hass.services.async_register(DOMAIN, SERVICE_COMPLETE, _handle_complete, schema=schema)
