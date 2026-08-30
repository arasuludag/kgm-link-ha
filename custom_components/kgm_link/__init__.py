"""The KGM Link integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KgmLinkApiError, KgmLinkAuthError, KgmLinkClient
from .const import CONF_PIN, CONF_REGION, DEFAULT_REGION, F_IS_EV
from .coordinator import KgmLinkCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
    Platform.LOCK,
    Platform.SWITCH,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
]

type KgmLinkConfigEntry = ConfigEntry[list[KgmLinkCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: KgmLinkConfigEntry) -> bool:
    """Set up KGM Link from a config entry."""
    client = KgmLinkClient(
        session=async_get_clientsession(hass),
        region=entry.data.get(CONF_REGION, DEFAULT_REGION),
        pin=entry.data.get(CONF_PIN),
    )
    try:
        await client.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
        vehicles = await client.async_get_vehicles()
    except KgmLinkAuthError as err:
        raise ConfigEntryAuthFailed from err
    except KgmLinkApiError as err:
        raise ConfigEntryNotReady from err

    coordinators: list[KgmLinkCoordinator] = []
    for vehicle in vehicles:
        if not vehicle.get(F_IS_EV):
            continue  # EV-only for now; ICE status is a different endpoint
        coordinator = KgmLinkCoordinator(hass, entry, client, vehicle)
        await coordinator.async_config_entry_first_refresh()
        await coordinator.async_load_detail()
        coordinators.append(coordinator)

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KgmLinkConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
