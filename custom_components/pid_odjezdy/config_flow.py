"""Config flow — Golemio token + název zastávky, options pro tabuli."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import (
    CANCELED_SHOW,
    CANCELED_SKIP,
    CONF_API_TOKEN,
    CONF_CANCELED_MODE,
    CONF_DEPARTURES_COUNT,
    CONF_MINUTES_AFTER,
    CONF_PLATFORM_FILTER,
    CONF_ROUTE_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STOP_NAME,
    DEFAULT_CANCELED_MODE,
    DEFAULT_DEPARTURES_COUNT,
    DEFAULT_MINUTES_AFTER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DEPARTURES_COUNT,
    MAX_MINUTES_AFTER,
    MAX_SCAN_INTERVAL,
    MIN_DEPARTURES_COUNT,
    MIN_MINUTES_AFTER,
    MIN_SCAN_INTERVAL,
)
from .golemio_client import (
    GolemioAuthError,
    GolemioClient,
    GolemioError,
    GolemioStopNotFound,
)


def _canceled_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=CANCELED_SKIP, label="skip"),
                SelectOptionDict(value=CANCELED_SHOW, label="show"),
            ],
            mode=SelectSelectorMode.LIST,
            translation_key=CONF_CANCELED_MODE,
        )
    )


def _options_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DEPARTURES_COUNT,
                default=current.get(CONF_DEPARTURES_COUNT, DEFAULT_DEPARTURES_COUNT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_DEPARTURES_COUNT,
                    max=MAX_DEPARTURES_COUNT,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MINUTES_AFTER,
                default=current.get(CONF_MINUTES_AFTER, DEFAULT_MINUTES_AFTER),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_MINUTES_AFTER,
                    max=MAX_MINUTES_AFTER,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_CANCELED_MODE,
                default=current.get(CONF_CANCELED_MODE, DEFAULT_CANCELED_MODE),
            ): _canceled_selector(),
            vol.Optional(
                CONF_ROUTE_FILTER,
                description={
                    "suggested_value": current.get(CONF_ROUTE_FILTER, "")
                },
            ): str,
            vol.Optional(
                CONF_PLATFORM_FILTER,
                description={
                    "suggested_value": current.get(CONF_PLATFORM_FILTER, "")
                },
            ): str,
        }
    )


class PidConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            stop_name = user_input[CONF_STOP_NAME].strip()

            await self.async_set_unique_id(slugify(stop_name))
            self._abort_if_unique_id_configured()

            client = GolemioClient(async_get_clientsession(self.hass), token)
            try:
                board = await client.fetch_board(
                    stop_name, limit=1, minutes_after=60, skip_canceled=True
                )
            except GolemioAuthError:
                errors[CONF_API_TOKEN] = "invalid_auth"
            except GolemioStopNotFound:
                errors[CONF_STOP_NAME] = "stop_not_found"
            except GolemioError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=board.stop_name or stop_name,
                    data={
                        CONF_API_TOKEN: token,
                        CONF_STOP_NAME: stop_name,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_STOP_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            client = GolemioClient(async_get_clientsession(self.hass), token)
            try:
                await client.fetch_board(
                    entry.data[CONF_STOP_NAME],
                    limit=1,
                    minutes_after=60,
                    skip_canceled=True,
                )
            except GolemioAuthError:
                errors[CONF_API_TOKEN] = "invalid_auth"
            except GolemioError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_API_TOKEN: token}
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return PidOptionsFlow()


class PidOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_DEPARTURES_COUNT] = int(
                user_input[CONF_DEPARTURES_COUNT]
            )
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            user_input[CONF_MINUTES_AFTER] = int(user_input[CONF_MINUTES_AFTER])
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(current)
        )
