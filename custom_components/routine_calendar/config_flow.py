"""Config flow for Routine Calendar."""
from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_DUE_DATE,
    CONF_ICON,
    CONF_ID,
    CONF_INTERVAL_UNIT,
    CONF_INTERVAL_VALUE,
    CONF_NAME,
    DOMAIN,
    INTERVAL_UNITS,
    UNIT_WEEKS,
)
from .coordinator import RoutineCalendarCoordinator


class RoutineCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial configuration flow - single instance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            await self.async_set_unique_id(slugify(name))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=name, data={})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_NAME): selector.TextSelector()}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RoutineCalendarOptionsFlow()


class RoutineCalendarOptionsFlow(OptionsFlow):
    """Manage routines: add, edit, remove."""

    def __init__(self) -> None:
        self._edit_routine_id: str | None = None

    @property
    def _coordinator(self) -> RoutineCalendarCoordinator:
        return self.hass.data[DOMAIN][self.config_entry.entry_id]

    # -------------------------------------------------------------- menu

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        options = ["add"]
        if self._coordinator.routines:
            options.extend(["edit", "remove"])
        return self.async_show_menu(step_id="init", menu_options=options)

    # --------------------------------------------------------------- add

    async def async_step_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                due_date = _parse_date(user_input[CONF_DUE_DATE])
            except ValueError:
                errors[CONF_DUE_DATE] = "invalid_date"
            else:
                await self._coordinator.async_add_routine(
                    name=user_input[CONF_NAME].strip(),
                    due_date=due_date,
                    interval_value=int(user_input[CONF_INTERVAL_VALUE]),
                    interval_unit=user_input[CONF_INTERVAL_UNIT],
                    icon=user_input.get(CONF_ICON) or None,
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add",
            data_schema=_routine_schema(
                name="",
                due_date=dt_util.now().date(),
                interval_value=1,
                interval_unit=UNIT_WEEKS,
            ),
            errors=errors,
        )

    # -------------------------------------------------------------- edit

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        routines = self._coordinator.routines
        if not routines:
            return self.async_abort(reason="no_routines")
        if user_input is not None:
            self._edit_routine_id = user_input[CONF_ID]
            return await self.async_step_edit_form()
        return self.async_show_form(
            step_id="edit",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=r[CONF_ID], label=r[CONF_NAME])
                                for r in routines
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._edit_routine_id is not None
        routine = self._coordinator.get(self._edit_routine_id)
        if routine is None:
            return self.async_abort(reason="unknown_routine")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                due_date = _parse_date(user_input[CONF_DUE_DATE])
            except ValueError:
                errors[CONF_DUE_DATE] = "invalid_date"
            else:
                await self._coordinator.async_update_routine(
                    self._edit_routine_id,
                    name=user_input[CONF_NAME].strip(),
                    due_date=due_date,
                    interval_value=int(user_input[CONF_INTERVAL_VALUE]),
                    interval_unit=user_input[CONF_INTERVAL_UNIT],
                    icon=user_input.get(CONF_ICON) or None,
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_form",
            data_schema=_routine_schema(
                name=routine[CONF_NAME],
                due_date=routine[CONF_DUE_DATE],
                interval_value=routine[CONF_INTERVAL_VALUE],
                interval_unit=routine[CONF_INTERVAL_UNIT],
                icon=routine.get(CONF_ICON),
            ),
            errors=errors,
            description_placeholders={"name": routine[CONF_NAME]},
        )

    # ------------------------------------------------------------ remove

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        routines = self._coordinator.routines
        if not routines:
            return self.async_abort(reason="no_routines")
        if user_input is not None:
            await self._coordinator.async_remove_routine(user_input[CONF_ID])
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=r[CONF_ID], label=r[CONF_NAME])
                                for r in routines
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )


def _routine_schema(
    *,
    name: str,
    due_date: date,
    interval_value: int,
    interval_unit: str,
    icon: str | None = None,
) -> vol.Schema:
    icon_kwargs = {"default": icon} if icon else {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): selector.TextSelector(),
            vol.Required(CONF_DUE_DATE, default=due_date.isoformat()): selector.DateSelector(),
            vol.Required(
                CONF_INTERVAL_VALUE, default=interval_value
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_INTERVAL_UNIT, default=interval_unit
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=INTERVAL_UNITS,
                    translation_key="interval_unit",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_ICON, **icon_kwargs): selector.IconSelector(),
        }
    )


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
