"""Config flow for KGM Link."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KgmLinkApiError, KgmLinkAuthError, KgmLinkClient
from .const import CONF_PIN, CONF_REGION, DEFAULT_REGION, DOMAIN

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PIN): str,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): str,
    }
)


class KgmLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the login flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = KgmLinkClient(
                session=async_get_clientsession(self.hass),
                region=user_input[CONF_REGION],
                pin=user_input.get(CONF_PIN),
            )
            try:
                await client.login(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            except KgmLinkAuthError:
                errors["base"] = "invalid_auth"
            except (KgmLinkApiError, Exception):  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )
