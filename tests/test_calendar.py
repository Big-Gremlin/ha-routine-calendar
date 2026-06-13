"""Tests for the calendar entity."""
from __future__ import annotations

from datetime import date, datetime, timezone

from homeassistant.core import HomeAssistant

from custom_components.routine_calendar.const import DOMAIN, UNIT_WEEKS


async def _setup(hass, entry):
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


class TestCalendar:
    async def test_calendar_entity_is_created(self, hass: HomeAssistant, entry):
        await _setup(hass, entry)
        state = hass.states.get("calendar.routine_calendar")
        assert state is not None

    async def test_get_events_returns_routines_in_window(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        await coordinator.async_add_routine(
            name="inside",
            due_date=date(2026, 6, 15),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )
        await coordinator.async_add_routine(
            name="outside",
            due_date=date(2026, 12, 1),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )
        await hass.async_block_till_done()

        result = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": "calendar.routine_calendar",
                "start_date_time": datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat(),
                "end_date_time": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            },
            blocking=True,
            return_response=True,
        )

        events = result["calendar.routine_calendar"]["events"]
        summaries = [e["summary"] for e in events]
        assert summaries == ["inside"]

    async def test_get_events_multiple_in_window(self, hass: HomeAssistant, entry):
        coordinator = await _setup(hass, entry)
        await coordinator.async_add_routine(
            name="first", due_date=date(2026, 6, 5), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await coordinator.async_add_routine(
            name="second", due_date=date(2026, 6, 20), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await coordinator.async_add_routine(
            name="outside", due_date=date(2026, 8, 1), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await hass.async_block_till_done()

        result = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": "calendar.routine_calendar",
                "start_date_time": datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat(),
                "end_date_time": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            },
            blocking=True,
            return_response=True,
        )

        summaries = [e["summary"] for e in result["calendar.routine_calendar"]["events"]]
        assert "first" in summaries
        assert "second" in summaries
        assert "outside" not in summaries

    async def test_calendar_state_off_when_no_routines(
        self, hass: HomeAssistant, entry
    ):
        await _setup(hass, entry)
        await hass.async_block_till_done()

        state = hass.states.get("calendar.routine_calendar")
        assert state.state == "off"

    async def test_calendar_state_off_when_all_routines_in_past(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        # Use a date clearly in the past so event property returns None.
        await coordinator.async_add_routine(
            name="old", due_date=date(2020, 1, 1), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await hass.async_block_till_done()

        state = hass.states.get("calendar.routine_calendar")
        assert state.state == "off"

    async def test_event_property_returns_soonest_upcoming(
        self, hass: HomeAssistant, entry
    ):
        coordinator = await _setup(hass, entry)
        # Both dates far in the future; added in reverse order.
        await coordinator.async_add_routine(
            name="later", due_date=date(2099, 12, 1), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await coordinator.async_add_routine(
            name="sooner", due_date=date(2099, 6, 1), interval_value=1, interval_unit=UNIT_WEEKS
        )
        await hass.async_block_till_done()

        state = hass.states.get("calendar.routine_calendar")
        assert state is not None
        # Events are in 2099 — not currently active, but event property must point to soonest.
        assert state.attributes.get("message") == "sooner"
