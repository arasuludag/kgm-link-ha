"""DataUpdateCoordinator for KGM Link.

Regular polling uses VehiclesChangeDetail — the same cached read the app shows on open:
no PIN, no wake, no 12 V cost. Fresh door states (CmdEv wake) and location
(LocationFinder) are on-demand only, since both wake the car and need the PIN.

Remote commands (lock, charge, climate, lights) go through `async_command`. Their real
outcome is only ever delivered to the app by Firebase push, which HA cannot receive, so
we mirror the app's own fallback: assume the command took, then re-read the free cached
endpoint a few seconds later to pick up whatever it can actually see.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KgmLinkApiError, KgmLinkAuthError, KgmLinkClient, KgmLinkPinError
from .const import (
    COMMAND_SETTLE_DELAYS_S,
    DEFAULT_CLIMATE_DURATION,
    DEFAULT_HVAC_TEMP,
    DEFAULT_HVAC_TEMP_MAX,
    DEFAULT_HVAC_TEMP_MIN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    F_HVAC_TEMP_MAX,
    F_HVAC_TEMP_MIN,
    F_IS_EV,
    F_MODEL_NAME,
    F_NICKNAME,
    F_VEHL_ID,
    F_VIN,
    SEAT_FIELDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ClimateSettings:
    """What the next climate start will ask for.

    RemoteEngineStartEv is a one-shot: it carries the temperature, how long to run, and
    every seat/defrost option in a single call. HA has no single entity shaped like
    that, so the companion number/switch/select entities write their values here and
    the climate entity reads them when it fires.
    """

    temperature: float = DEFAULT_HVAC_TEMP
    duration: int = DEFAULT_CLIMATE_DURATION
    defrost: bool = False
    rear_window_heat: bool = False
    seats: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(SEAT_FIELDS, 0)
    )


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
        self.detail: dict[str, Any] = {}
        self.climate_settings = ClimateSettings()
        self._location: dict[str, Any] | None = None
        # Door/lock/hood states exist only in the wake payload, so they must survive
        # the cached polls that follow — otherwise every 15-minute poll would blank them.
        self._wake: dict[str, Any] = {}
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

    @property
    def min_temp(self) -> float:
        """Cabin temperature floor, as the vehicle reports it."""
        return float(self.detail.get(F_HVAC_TEMP_MIN) or DEFAULT_HVAC_TEMP_MIN)

    @property
    def max_temp(self) -> float:
        return float(self.detail.get(F_HVAC_TEMP_MAX) or DEFAULT_HVAC_TEMP_MAX)

    async def async_load_detail(self) -> None:
        """Read the static vehicle detail once, for the HVAC bounds."""
        try:
            self.detail = await self.client.async_get_vehicle_detail(self.vehicle_id)
        except KgmLinkApiError as err:
            _LOGGER.debug("Vehicle detail unavailable (%s); using default HVAC bounds", err)

    async def _async_update_data(self) -> dict[str, Any]:
        """Free cached read (SoC/range/charging). Keeps wake-only state and location."""
        try:
            cached = await self.client.async_read_cached(self.vehicle_id)
        except KgmLinkAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KgmLinkApiError as err:
            raise UpdateFailed(str(err)) from err
        return {**self._wake, **cached, "location": self._location}

    async def async_locate(self) -> None:
        """On-demand: wake the car and fetch its GPS position. Needs the PIN."""
        self._location = await self.client.async_refresh_location(self.vehicle_id)
        self.async_set_updated_data({**(self.data or {}), "location": self._location})

    async def async_wake_refresh(self) -> None:
        """On-demand: wake the car for fresh door/lock + SoC. Needs the PIN."""
        self._wake = await self.client.async_refresh_status(self.vehicle_id)
        self.async_set_updated_data(
            {**(self.data or {}), **self._wake, "location": self._location}
        )

    async def async_command(
        self,
        action: Callable[[], Awaitable[Any]],
        *,
        optimistic: dict[str, Any] | None = None,
        persist: bool = False,
    ) -> None:
        """Fire a remote command, assume it worked, then re-read what we can for free.

        `optimistic` is shown immediately so the UI does not snap back under the user.
        Set `persist` only for fields the cached poll cannot see (door locks) — those
        have to be remembered, whereas anything the poll returns should be allowed to
        correct itself.

        Raises HomeAssistantError so the failure surfaces in the UI on the entity the
        user just pressed, rather than only in the log.
        """
        try:
            await action()
        except KgmLinkPinError as err:
            raise HomeAssistantError(f"KGM Link remote PIN problem: {err}") from err
        except KgmLinkApiError as err:
            raise HomeAssistantError(f"KGM Link command failed: {err}") from err

        if optimistic:
            if persist:
                self._wake.update(optimistic)
            self.async_set_updated_data({**(self.data or {}), **optimistic})

        for delay in COMMAND_SETTLE_DELAYS_S:
            async_call_later(self.hass, delay, self._async_settle)

    async def _async_settle(self, _now: Any) -> None:
        await self.async_request_refresh()
