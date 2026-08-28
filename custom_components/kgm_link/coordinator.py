"""DataUpdateCoordinator for KGM Link.

Regular polling uses VehiclesChangeDetail — the same cached read the app shows on open:
no PIN, no wake, no 12 V cost. Fresh door states (CmdEv wake) and location
(LocationFinder) are on-demand only, since both wake the car and need the PIN.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KgmLinkApiError, KgmLinkAuthError, KgmLinkClient, KgmLinkPinError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    F_IS_EV,
    F_MODEL_NAME,
    F_NICKNAME,
    F_VEHL_ID,
    F_VIN,
)

_LOGGER = logging.getLogger(__name__)


class KgmLinkCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinates one vehicle's telemetry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: KgmLinkClient,
        vehicle: dict[str, Any],
    ) -> None:
        self.vehicle = vehicle
        self.vehicle_id: int = vehicle[F_VEHL_ID]
        self._location: dict[str, Any] | None = None
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}:{self.vehicle_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.entry = entry
        self.client = client

    @property
    def device_name(self) -> str:
        return self.vehicle.get(F_NICKNAME) or self.vehicle.get(F_MODEL_NAME) or "KGM vehicle"

    @property
    def model(self) -> str | None:
        return self.vehicle.get(F_MODEL_NAME)

    @property
    def vin(self) -> str | None:
        return self.vehicle.get(F_VIN)

    @property
    def is_ev(self) -> bool:
        return bool(self.vehicle.get(F_IS_EV))

    async def _async_update_data(self) -> dict[str, Any]:
        """Free cached read (SoC/range/charging). Keeps last-known location."""
        try:
            cached = await self.client.async_read_cached(self.vehicle_id)
        except KgmLinkAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KgmLinkApiError as err:
            raise UpdateFailed(str(err)) from err
        return {**cached, "location": self._location}

    async def async_locate(self) -> None:
        """On-demand: wake the car and fetch its GPS position. Needs the PIN."""
        self._location = await self.client.async_refresh_location(self.vehicle_id)
        self.async_set_updated_data({**(self.data or {}), "location": self._location})

    async def async_wake_refresh(self) -> None:
        """On-demand: wake the car for fresh door/lock + SoC. Needs the PIN."""
        fresh = await self.client.async_refresh_status(self.vehicle_id)
        self.async_set_updated_data({**(self.data or {}), **fresh, "location": self._location})
