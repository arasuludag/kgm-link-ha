"""KGM Link climate (remote preconditioning).

RemoteEngineStartEv is a one-shot, not a thermostat: one call carries the target
temperature, the run time, defrost, rear-window heat and all six seat levels, and the
car shuts the session down by itself when the time is up. So this entity is
`assumed_state` — it reports what we asked for, and returns to off when the run time
elapses. The companion number/switch/select entities supply the rest of the payload.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import KgmLinkConfigEntry
from .const import HVAC_TEMP_STEP
from .coordinator import KgmLinkCoordinator
from .entity import KgmLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(KgmLinkClimate(c) for c in entry.runtime_data)


class KgmLinkClimate(KgmLinkEntity, ClimateEntity):
    _attr_translation_key = "climate"
    _attr_assumed_state = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = HVAC_TEMP_STEP
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: KgmLinkCoordinator) -> None:
        super().__init__(coordinator, "climate")
        self._running = False
        self._cancel_auto_off: Any = None

    @property
    def min_temp(self) -> float:
        return self.coordinator.min_temp

    @property
    def max_temp(self) -> float:
        return self.coordinator.max_temp

    @property
    def target_temperature(self) -> float:
        return self.coordinator.climate_settings.temperature

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT_COOL if self._running else HVACMode.OFF

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        settings = self.coordinator.climate_settings
        return {
            "run_time_minutes": settings.duration,
            "defrost": settings.defrost,
            "rear_window_heat": settings.rear_window_heat,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self.coordinator.climate_settings.temperature = float(temperature)
        self.async_write_ha_state()
        if self._running:
            # Re-send so the change actually reaches the car mid-run.
            await self._start()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self._start()

    async def async_turn_off(self) -> None:
        await self.coordinator.async_command(
            lambda: self.coordinator.client.async_stop_climate(
                self.coordinator.vehicle_id
            )
        )
        self._set_running(False)

    async def _start(self) -> None:
        settings = self.coordinator.climate_settings
        await self.coordinator.async_command(
            lambda: self.coordinator.client.async_start_climate(
                self.coordinator.vehicle_id,
                temperature=settings.temperature,
                duration=settings.duration,
                defrost=settings.defrost,
                rear_window_heat=settings.rear_window_heat,
                seats=settings.seats,
            )
        )
        self._set_running(True, auto_off_after=settings.duration * 60)

    def _set_running(self, running: bool, auto_off_after: float | None = None) -> None:
        if self._cancel_auto_off is not None:
            self._cancel_auto_off()
            self._cancel_auto_off = None
        self._running = running
        if running and auto_off_after:
            self._cancel_auto_off = async_call_later(
                self.hass, auto_off_after, self._auto_off
            )
        self.async_write_ha_state()

    @callback
    def _auto_off(self, _now: Any) -> None:
        """The car stops on its own once the run time is up."""
        self._cancel_auto_off = None
        self._running = False
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_auto_off is not None:
            self._cancel_auto_off()
            self._cancel_auto_off = None
        await super().async_will_remove_from_hass()
