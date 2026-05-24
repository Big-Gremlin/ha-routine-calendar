"""Tests for the per-routine 'last completed' date entity."""
from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant

from custom_components.routine_calendar.const import (
    CONF_DUE_DATE,
    CONF_LAST_COMPLETED,
    DOMAIN,
    UNIT_WEEKS,
)


async def _setup(hass, entry):
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


class TestDateEntity:
    async def test_entity_created_for_existing_routine(
        self, hass: HomeAssistant, entry
    ):
        # Add routine before setup so it's present at load time
        from unittest.mock import AsyncMock, MagicMock, patch

        stored = {
            "routines": [
                {
                    "id": "abc",
                    "name": "Blumen gießen",
                    "due_date": "2026-05-23",
                    "interval_value": 1,
                    "interval_unit": "weeks",
                    "last_completed": "2026-05-16",
                }
            ]
        }
        with patch("custom_components.routine_calendar.coordinator.Store") as MockStore:
            inst = MagicMock()
            inst.async_load = AsyncMock(return_value=stored)
            inst.async_delay_save = MagicMock()
            inst.async_save = AsyncMock()
            MockStore.return_value = inst
            await _setup(hass, entry)

        states = [
            s for s in hass.states.async_all() if s.entity_id.startswith("date.")
        ]
        assert len(states) == 1
        assert states[0].state == "2026-05-16"

    async def test_entity_created_when_routine_added_at_runtime(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)

        await coordinator.async_add_routine(
            name="Blumen gießen",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )
        await hass.async_block_till_done()

        date_states = [
            s for s in hass.states.async_all() if s.entity_id.startswith("date.")
        ]
        assert len(date_states) == 1

    async def test_setting_date_entity_recomputes_due_date(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="Blumen gießen",
            due_date=date(2026, 5, 16),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )
        await hass.async_block_till_done()

        date_state = next(
            s for s in hass.states.async_all() if s.entity_id.startswith("date.")
        )

        await hass.services.async_call(
            "date",
            "set_value",
            {"entity_id": date_state.entity_id, "date": "2026-05-17"},
            blocking=True,
        )

        routine = coordinator.get(rid)
        assert routine[CONF_LAST_COMPLETED] == date(2026, 5, 17)
        assert routine[CONF_DUE_DATE] == date(2026, 5, 24)

    async def test_entity_state_unknown_when_no_last_completed(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        await coordinator.async_add_routine(
            name="new",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )
        await hass.async_block_till_done()

        date_state = next(
            s for s in hass.states.async_all() if s.entity_id.startswith("date.")
        )
        assert date_state.state == "unknown"

    async def test_multiple_routines_create_multiple_date_entities(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        await coordinator.async_add_routine(
            name="A", due_date=date(2026, 5, 23), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await coordinator.async_add_routine(
            name="B", due_date=date(2026, 6, 1), interval_value=2, interval_unit=UNIT_WEEKS
        )
        await hass.async_block_till_done()

        date_states = [s for s in hass.states.async_all() if s.entity_id.startswith("date.")]
        assert len(date_states) == 2

    async def test_entity_removed_when_routine_deleted(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="doomed",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )
        await hass.async_block_till_done()

        date_states_before = [
            s for s in hass.states.async_all() if s.entity_id.startswith("date.")
        ]
        assert len(date_states_before) == 1
        entity_id = date_states_before[0].entity_id

        await coordinator.async_remove_routine(rid)
        await hass.async_block_till_done()

        assert hass.states.get(entity_id) is None
