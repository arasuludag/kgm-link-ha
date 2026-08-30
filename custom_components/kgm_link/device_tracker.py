"""KGM Link car location (device_tracker).

Location isn't in the cached read — it comes from an on-demand wake (LocationFinder).
This tracker reports the last position fetched via the "Locate" button / service.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .const import F_LAT, F_LON
from .coordinator import KgmLinkCoordinator
from .entity import KgmLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(KgmLinkTracker(c) for c in entry.runtime_data)


class KgmLinkTracker(KgmLinkEntity, TrackerEntity):
    _attr_translation_key = "car"

    def __init__(self, coordinator: KgmLinkCoordinator) -> None:
        super().__init__(coordinator, "location")

    def _loc(self) -> dict[str, Any]:
        return self.status.get("location") or {}

    @property
    def latitude(self) -> float | None:
        return self._loc().get(F_LAT)

    @property
    def longitude(self) -> float | None:
        return self._loc().get(F_LON)
