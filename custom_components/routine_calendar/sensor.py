"""Sensor platform: one 'days until due' entity per routine."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DUE_DATE,
    CONF_ICON,
    CONF_ID,
    CONF_INTERVAL_UNIT,
    CONF_INTERVAL_VALUE,
    CONF_NAME,
    DOMAIN,
    SIGNAL_ROUTINES_CHANGED,
)
from .coordinator import RoutineCalendarCoordinator

_DESCRIPTION = SensorEntityDescription(
    key="days_until_due",
    translation_key="next_due",
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoutineCalendarCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = set()

    @callback
    def _sync_entities() -> None:
        current_ids = {r[CONF_ID] for r in coordinator.routines}
        new_ids = current_ids - known
        if new_ids:
            async_add_entities(
                [RoutineDaysUntilDueEntity(coordinator, rid) for rid in new_ids]
            )
            known.update(new_ids)
        known.intersection_update(current_ids)

    _sync_entities()

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_ROUTINES_CHANGED, _sync_entities)
    )


class RoutineDaysUntilDueEntity(SensorEntity):
    """Read-only sensor: days until (or since) a routine is due.

    Positive = due in N days, 0 = due today, negative = overdue by N days.
    """

    _attr_has_entity_name = True
    entity_description = _DESCRIPTION

    def __init__(
        self, coordinator: RoutineCalendarCoordinator, routine_id: str
    ) -> None:
        self._coordinator = coordinator
        self._routine_id = routine_id
        self._attr_unique_id = f"{DOMAIN}_{routine_id}_next_due"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ROUTINES_CHANGED, self._handle_change
            )
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        routine = self._coordinator.get(self._routine_id)
        if routine is None:
            return None
        interval = f"{routine[CONF_INTERVAL_VALUE]} {routine[CONF_INTERVAL_UNIT]}"
        return DeviceInfo(
            identifiers={(DOMAIN, self._routine_id)},
            name=routine[CONF_NAME],
            entry_type=DeviceEntryType.SERVICE,
            model=f"alle {interval}",
            manufacturer="Routine Calendar",
        )

    @callback
    def _handle_change(self) -> None:
        if self._coordinator.get(self._routine_id) is not None:
            self.async_write_ha_state()
            return
        entity_registry = er.async_get(self.hass)
        if self.entity_id and entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._routine_id)}
        )
        if device and not er.async_entries_for_device(entity_registry, device.id):
            device_registry.async_remove_device(device.id)

    @property
    def icon(self) -> str | None:
        routine = self._coordinator.get(self._routine_id)
        return routine.get(CONF_ICON) if routine else None

    @property
    def native_value(self) -> int | None:
        routine = self._coordinator.get(self._routine_id)
        if routine is None:
            return None
        return (routine[CONF_DUE_DATE] - dt_util.now().date()).days

    @property
    def available(self) -> bool:
        return self._coordinator.get(self._routine_id) is not None
