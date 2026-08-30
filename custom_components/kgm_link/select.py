"""KGM Link selects — per-seat heating and ventilation for the next climate start."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .const import SEAT_LEVEL_OPTIONS, SEAT_LEVELS
from .coordinator import KgmLinkCoordinator
from .entity import KgmLinkSettingEntity

# field name in RemoteEngineStartV1Body -> (translation key, on by default?)
# Only the front seats are enabled out of the box; rear rows exist on some trims and
# would otherwise just be clutter, so they ship disabled but available.
SEATS: dict[str, tuple[str, bool]] = {
    "driveSeat": ("seat_driver", True),
    "passengerSeat": ("seat_passenger", True),
    "secondLeftSeat": ("seat_second_left", False),
    "secondRightSeat": ("seat_second_right", False),
    "thirdLeftSeat": ("seat_third_left", False),
    "thirdRightSeat": ("seat_third_right", False),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        KgmLinkSeatSelect(coordinator, field, key, default_on)
        for coordinator in entry.runtime_data
        for field, (key, default_on) in SEATS.items()
    )


class KgmLinkSeatSelect(KgmLinkSettingEntity, SelectEntity):
    _attr_options = SEAT_LEVEL_OPTIONS

    def __init__(
        self,
        coordinator: KgmLinkCoordinator,
        field: str,
        translation_key: str,
        default_on: bool,
    ) -> None:
        super().__init__(coordinator, translation_key)
        self._field = field
        self._attr_translation_key = translation_key
        self._attr_entity_registry_enabled_default = default_on

    @property
    def current_option(self) -> str:
        level = self.coordinator.climate_settings.seats.get(self._field, 0)
        return next(
            (name for name, value in SEAT_LEVELS.items() if value == level), "off"
        )

    async def async_select_option(self, option: str) -> None:
        self.coordinator.climate_settings.seats[self._field] = SEAT_LEVELS[option]
        self.async_write_ha_state()

    def restore(self, value: str) -> None:
        if value in SEAT_LEVELS:
            self.coordinator.climate_settings.seats[self._field] = SEAT_LEVELS[value]
