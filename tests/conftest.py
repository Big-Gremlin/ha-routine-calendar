"""Shared test fixtures."""
from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.routine_calendar.const import DOMAIN


@pytest.fixture
def entry(hass):
    """Bare config entry — routines live in storage, not options."""
    e = MockConfigEntry(domain=DOMAIN, data={}, options={}, unique_id=DOMAIN)
    e.add_to_hass(hass)
    return e


@pytest.fixture
async def setup_integration(hass, entry):
    """Set up the integration and return the coordinator."""
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]
