"""Tests for the config & options flows."""
from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.routine_calendar.const import (
    CONF_DUE_DATE,
    CONF_ID,
    CONF_INTERVAL_UNIT,
    CONF_INTERVAL_VALUE,
    CONF_NAME,
    DOMAIN,
    UNIT_DAYS,
    UNIT_WEEKS,
)


class TestConfigFlow:
    async def test_user_step_creates_entry(self, hass: HomeAssistant):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Routine Calendar"

    async def test_second_instance_is_rejected(self, hass: HomeAssistant, entry):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


class TestOptionsFlow:
    async def test_add_routine_via_options(self, hass: HomeAssistant, entry):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert "add" in result["menu_options"]

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "add"}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Blumen gießen",
                CONF_DUE_DATE: "2026-05-23",
                CONF_INTERVAL_VALUE: 1,
                CONF_INTERVAL_UNIT: UNIT_WEEKS,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert len(coordinator.routines) == 1
        assert coordinator.routines[0][CONF_NAME] == "Blumen gießen"

    async def test_remove_routine_via_options(self, hass: HomeAssistant, entry):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]
        from datetime import date
        rid = await coordinator.async_add_routine(
            name="doomed",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "remove"}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_ID: rid}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

        assert coordinator.get(rid) is None

    async def test_edit_routine_via_options(self, hass: HomeAssistant, entry):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        from datetime import date
        coordinator = hass.data[DOMAIN][entry.entry_id]
        rid = await coordinator.async_add_routine(
            name="old name",
            due_date=date(2026, 5, 23),
            interval_value=1,
            interval_unit=UNIT_WEEKS,
        )

        # Step 1: open options menu → pick edit
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert "edit" in result["menu_options"]

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "edit"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"

        # Step 2: select which routine to edit
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_ID: rid}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit_form"

        # Step 3: submit updated values
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "new name",
                CONF_DUE_DATE: "2026-07-01",
                CONF_INTERVAL_VALUE: 2,
                CONF_INTERVAL_UNIT: UNIT_WEEKS,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

        routine = coordinator.get(rid)
        assert routine[CONF_NAME] == "new name"
        assert routine[CONF_DUE_DATE] == date(2026, 7, 1)

    async def test_menu_has_no_edit_remove_when_no_routines(
        self, hass: HomeAssistant, entry
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert "add" in result["menu_options"]
        assert "edit" not in result["menu_options"]
        assert "remove" not in result["menu_options"]
