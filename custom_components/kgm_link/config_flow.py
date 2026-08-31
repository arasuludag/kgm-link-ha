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

STEP_REAUTH = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PIN): str,
    }
)


class KgmLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the login flow."""

    VERSION = 1

    async def _async_try_login(
        self, email: str, password: str, pin: str | None, region: str
    ) -> str | None:
        """Return an error key, or None when the credentials work."""
        client = KgmLinkClient(
            session=async_get_clientsession(self.hass),
            region=region,
            pin=pin,
            email=email,
            password=password,
        )
        try:
            await client.login(email, password)
        except KgmLinkAuthError:
            return "invalid_auth"
        except (KgmLinkApiError, Exception):  # noqa: BLE001
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_try_login(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input.get(CONF_PIN),
                user_input[CONF_REGION],
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Triggered when the stored credentials stop working.

        The integration recovers an expired session on its own by logging back in, so
        reaching here means the password itself is no longer valid — a changed password,
        or an account that needs attention in the app.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_try_login(
                entry.data[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input.get(CONF_PIN, entry.data.get(CONF_PIN)),
                entry.data.get(CONF_REGION, DEFAULT_REGION),
            )
            if error:
                errors["base"] = error
            else:
                updates = {CONF_PASSWORD: user_input[CONF_PASSWORD]}
                if user_input.get(CONF_PIN):
                    updates[CONF_PIN] = user_input[CONF_PIN]
                return self.async_update_reload_and_abort(entry, data_updates=updates)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH,
            errors=errors,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
        )
