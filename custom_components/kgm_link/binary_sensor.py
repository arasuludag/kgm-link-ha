"""KGM Link binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KgmLinkConfigEntry
from .const import CHARGING_ACTIVE, DOMAIN, F_CHARGING_STAT


@dataclass(frozen=True, kw_only=True)
class KgmBinary(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[KgmBinary, ...] = (
    KgmBinary(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda s: s.get(F_CHARGING_STAT) in CHARGING_ACTIVE
        if s.get(F_CHARGING_STAT) is not None
        else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[KgmLinkBinarySensor] = []
    for coordinator in entry.runtime_data:
        entities.extend(KgmLinkBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)
    async_add_entities(entities)


class KgmLinkBinarySensor(CoordinatorEntity, BinarySensorEntity):
    entity_description: KgmBinary
    _attr_has_entity_name = True

    def __init__(self, coordinator, description: KgmBinary) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.vehicle_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.vehicle_id))},
            manufacturer="KG Mobility",
            name=coordinator.device_name,
            model=coordinator.model,
            serial_number=coordinator.vin,
        )

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data or {})
