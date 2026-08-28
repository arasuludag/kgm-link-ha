"""KGM Link car location (device_tracker).

Location isn't in the cached read — it comes from an on-demand wake (LocationFinder).
This tracker reports the last position fetched via the "Locate" button / service.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KgmLinkConfigEntry
from .const import DOMAIN, F_LAT, F_LON


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(KgmLinkTracker(c) for c in entry.runtime_data)


class KgmLinkTracker(CoordinatorEntity, TrackerEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "car"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_location"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.vehicle_id))},
            manufacturer="KG Mobility",
            name=coordinator.device_name,
            model=coordinator.model,
            serial_number=coordinator.vin,
        )

    def _loc(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("location") or {}

    @property
    def latitude(self) -> float | None:
        return self._loc().get(F_LAT)

    @property
    def longitude(self) -> float | None:
        return self._loc().get(F_LON)
