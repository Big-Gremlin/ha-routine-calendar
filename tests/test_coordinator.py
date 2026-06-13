"""Integration tests for RoutineCalendarCoordinator.

Uses a real HomeAssistant instance via pytest-homeassistant-custom-component.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.routine_calendar.const import (
    ATTR_COMPLETED_ON,
    ATTR_ROUTINE_ID,
    CONF_DUE_DATE,
    CONF_LAST_COMPLETED,
    CONF_NAME,
    DOMAIN,
    SERVICE_COMPLETE,
    UNIT_DAYS,
    UNIT_WEEKS,
    CONF_INTERVAL_VALUE,
    CONF_INTERVAL_UNIT,
)


async def _setup(hass: HomeAssistant, entry):
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


# ---------------------------------------------------------------------------
# CRUD on routines
# ---------------------------------------------------------------------------


class TestRoutineCrud:
    async def test_add_routine_returns_id_and_persists(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)

        rid = await coordinator.async_add_routine(
            name="Blumen gießen",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )

        assert coordinator.get(rid)[CONF_NAME] == "Blumen gießen"
        assert coordinator.get(rid)[CONF_DUE_DATE] == date(2026, 5, 23)

    async def test_remove_routine(self, hass: HomeAssistant, entry):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="x",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )

        await coordinator.async_remove_routine(rid)

        assert coordinator.get(rid) is None

    async def test_update_routine_name(self, hass: HomeAssistant, entry):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="old", due_date=date(2026, 5, 23), interval_value=1, interval_unit=UNIT_WEEKS
        )

        await coordinator.async_update_routine(rid, name="new")

        assert coordinator.get(rid)[CONF_NAME] == "new"

    async def test_routines_sorted_by_due_date(self, hass: HomeAssistant, entry):
        coordinator = await _setup(hass, entry)
        await coordinator.async_add_routine(
            name="later", due_date=date(2026, 6, 1), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await coordinator.async_add_routine(
            name="sooner", due_date=date(2026, 5, 20), interval_value=1, interval_unit=UNIT_WEEKS
        )

        names = [r[CONF_NAME] for r in coordinator.routines]
        assert names == ["sooner", "later"]


# ---------------------------------------------------------------------------
# Completion logic
# ---------------------------------------------------------------------------


class TestCompletion:
    async def test_complete_anchors_next_due_to_completion_date(
        self, hass: HomeAssistant, entry
    ):
        """User example: due Sat, completed Sun → next due is the following Sun."""
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="Blumen gießen",
            due_date=date(2026, 5, 16),  # Saturday
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )

        await coordinator.async_complete(rid, completed_on=date(2026, 5, 17))  # Sunday

        routine = coordinator.get(rid)
        assert routine[CONF_LAST_COMPLETED] == date(2026, 5, 17)
        assert routine[CONF_DUE_DATE] == date(2026, 5, 24)

    async def test_complete_when_finished_early(self, hass: HomeAssistant, entry):
        """Same rule applies when completing before the due date."""
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="Blumen gießen",
            due_date=date(2026, 5, 16),  # Saturday
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )

        await coordinator.async_complete(rid, completed_on=date(2026, 5, 14))  # Thursday

        assert coordinator.get(rid)[CONF_DUE_DATE] == date(2026, 5, 21)

    async def test_complete_without_date_uses_today(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="x",
            due_date=date(2026, 5, 16),
            interval_value=3,
            interval_unit=UNIT_DAYS,
        )

        fixed_today = dt_util.now().date()
        await coordinator.async_complete(rid)

        from datetime import timedelta
        assert coordinator.get(rid)[CONF_DUE_DATE] == fixed_today + timedelta(days=3)

    async def test_set_last_completed_observer_recomputes_due(
        self, hass: HomeAssistant, entry
    ):
        """Setting last_completed (via Date entity / direct call) re-anchors due date."""
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="x",
            due_date=date(2026, 5, 16),
            interval_value=2,
            interval_unit=UNIT_WEEKS,
        )

        await coordinator.async_set_last_completed(rid, date(2026, 5, 10))

        routine = coordinator.get(rid)
        assert routine[CONF_LAST_COMPLETED] == date(2026, 5, 10)
        assert routine[CONF_DUE_DATE] == date(2026, 5, 24)

    async def test_complete_unknown_routine_raises(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        with pytest.raises(KeyError):
            await coordinator.async_complete("does-not-exist")


# ---------------------------------------------------------------------------
# Service registration
# ---------------------------------------------------------------------------


class TestService:
    async def test_complete_service_marks_routine(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="x",
            due_date=date(2026, 5, 16),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_COMPLETE,
            {ATTR_ROUTINE_ID: rid, ATTR_COMPLETED_ON: "2026-05-17"},
            blocking=True,
        )

        assert coordinator.get(rid)[CONF_DUE_DATE] == date(2026, 5, 24)

    async def test_complete_service_without_date_uses_today(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="x",
            due_date=date(2026, 5, 16),
            interval_value=1,
            interval_unit=UNIT_DAYS,
        )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_COMPLETE,
            {ATTR_ROUTINE_ID: rid},
            blocking=True,
        )

        from datetime import timedelta
        assert coordinator.get(rid)[CONF_DUE_DATE] == dt_util.now().date() + timedelta(days=1)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    async def test_stored_routines_are_loaded_on_setup(
        self, hass: HomeAssistant, entry
    ):
        from unittest.mock import AsyncMock, MagicMock

        stored = {
            "routines": [
                {
                    "id": "abc",
                    "name": "stored",
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

            coordinator = await _setup(hass, entry)

        routine = coordinator.get("abc")
        assert routine[CONF_NAME] == "stored"
        assert routine[CONF_DUE_DATE] == date(2026, 5, 23)
        assert routine[CONF_LAST_COMPLETED] == date(2026, 5, 16)

    async def test_stored_routine_with_null_last_completed(
        self, hass: HomeAssistant, entry
    ):
        from unittest.mock import AsyncMock, MagicMock

        stored = {
            "routines": [
                {
                    "id": "xyz",
                    "name": "never done",
                    "due_date": "2026-06-01",
                    "interval_value": 7,
                    "interval_unit": "days",
                    "last_completed": None,
                }
            ]
        }

        with patch("custom_components.routine_calendar.coordinator.Store") as MockStore:
            inst = MagicMock()
            inst.async_load = AsyncMock(return_value=stored)
            inst.async_delay_save = MagicMock()
            inst.async_save = AsyncMock()
            MockStore.return_value = inst

            coordinator = await _setup(hass, entry)

        routine = coordinator.get("xyz")
        assert routine is not None
        assert routine[CONF_LAST_COMPLETED] is None

    async def test_malformed_stored_routine_is_skipped(
        self, hass: HomeAssistant, entry
    ):
        from unittest.mock import AsyncMock, MagicMock

        stored = {
            "routines": [
                {"id": "bad"},  # missing required fields
                {
                    "id": "good",
                    "name": "ok",
                    "due_date": "2026-06-01",
                    "interval_value": 1,
                    "interval_unit": "weeks",
                    "last_completed": None,
                },
            ]
        }

        with patch("custom_components.routine_calendar.coordinator.Store") as MockStore:
            inst = MagicMock()
            inst.async_load = AsyncMock(return_value=stored)
            inst.async_delay_save = MagicMock()
            inst.async_save = AsyncMock()
            MockStore.return_value = inst

            coordinator = await _setup(hass, entry)

        assert coordinator.get("bad") is None
        assert coordinator.get("good") is not None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    async def test_add_routine_rejects_invalid_unit(
        self, hass: HomeAssistant, entry
    ):
        import voluptuous as vol

        coordinator = await _setup(hass, entry)
        with pytest.raises(vol.Invalid):
            await coordinator.async_add_routine(
                name="x",
                due_date=date(2026, 5, 23),
                interval_value=1,
                interval_unit="fortnights",
            )

    async def test_add_routine_rejects_zero_value(
        self, hass: HomeAssistant, entry
    ):
        import voluptuous as vol

        coordinator = await _setup(hass, entry)
        with pytest.raises(vol.Invalid):
            await coordinator.async_add_routine(
                name="x",
                due_date=date(2026, 5, 23),
                interval_value=0,
                interval_unit=UNIT_WEEKS,
            )

    async def test_update_routine_unknown_id_raises(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        with pytest.raises(KeyError):
            await coordinator.async_update_routine("no-such-id", name="new")

    async def test_update_routine_invalid_unit_raises(
        self, hass: HomeAssistant, entry
    ):
        import voluptuous as vol

        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="x", due_date=date(2026, 5, 23), interval_value=1, interval_unit=UNIT_WEEKS
        )
        with pytest.raises(vol.Invalid):
            await coordinator.async_update_routine(rid, interval_unit="fortnights")

    async def test_update_routine_all_fields(self, hass: HomeAssistant, entry):
        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="old", due_date=date(2026, 5, 23), interval_value=1, interval_unit=UNIT_WEEKS
        )

        await coordinator.async_update_routine(
            rid,
            name="new",
            due_date=date(2026, 6, 1),
            interval_value=3,
            interval_unit=UNIT_DAYS,
        )

        routine = coordinator.get(rid)
        assert routine[CONF_NAME] == "new"
        assert routine[CONF_DUE_DATE] == date(2026, 6, 1)
        assert routine["interval_value"] == 3
        assert routine["interval_unit"] == UNIT_DAYS

    async def test_remove_nonexistent_routine_is_noop(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        # Should not raise.
        await coordinator.async_remove_routine("ghost-id")

    async def test_remove_routine_cleans_up_disabled_device(
        self, hass: HomeAssistant, entry
    ):
        """Deleting a routine whose device/entities are disabled must still
        remove them from the registries (they never receive the dispatcher
        signal because disabled entities are not loaded into hass)."""
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers.entity_registry import RegistryEntryDisabler

        coordinator = await _setup(hass, entry)
        rid = await coordinator.async_add_routine(
            name="doomed",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )
        await hass.async_block_till_done()

        entity_reg = er.async_get(hass)
        device_reg = dr.async_get(hass)
        device = device_reg.async_get_device(identifiers={("routine_calendar", rid)})
        assert device is not None

        # Disable all entities of the device (simulates user disabling the device).
        for entry_item in er.async_entries_for_device(entity_reg, device.id):
            entity_reg.async_update_entity(
                entry_item.entity_id, disabled_by=RegistryEntryDisabler.USER
            )
        await hass.async_block_till_done()

        # Delete the routine — coordinator must clean up registry despite no live listeners.
        await coordinator.async_remove_routine(rid)
        await hass.async_block_till_done()

        assert device_reg.async_get_device(identifiers={("routine_calendar", rid)}) is None
        assert (
            er.async_entries_for_device(entity_reg, device.id, include_disabled_entities=True)
            == []
        )

    async def test_complete_service_unknown_routine_logs_warning(
        self, hass: HomeAssistant, entry, caplog: pytest.LogCaptureFixture
    ):
        import logging

        await _setup(hass, entry)

        with caplog.at_level(logging.WARNING):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_COMPLETE,
                {ATTR_ROUTINE_ID: "no-such-id"},
                blocking=True,
            )

        assert any("no-such-id" in rec.message for rec in caplog.records)
