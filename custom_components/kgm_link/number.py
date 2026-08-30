"""KGM Link numbers — how long remote climate should run."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .const import MAX_CLIMATE_DURATION, MIN_CLIMATE_DURATION
from .coordinator import KgmLinkCoordinator
from .entity import KgmLinkSettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(KgmLinkClimateDuration(c) for c in entry.runtime_data)


class KgmLinkClimateDuration(KgmLinkSettingEntity, NumberEntity):
    """Minutes the car will run climate before shutting itself off.

    The app's own picker stops at 10 minutes, so this does too.
    """

    _attr_translation_key = "climate_duration"
    _attr_native_min_value = MIN_CLIMATE_DURATION
    _attr_native_max_value = MAX_CLIMATE_DURATION
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: KgmLinkCoordinator) -> None:
        super().__init__(coordinator, "climate_duration")

    @property
    def native_value(self) -> float:
        return self.coordinator.climate_settings.duration

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.climate_settings.duration = int(value)
        self.async_write_ha_state()

    def restore(self, value: str) -> None:
        try:
            self.coordinator.climate_settings.duration = int(float(value))
        except ValueError:
            pass
