"""KGM Link binary sensors.

Charging comes from the free cached poll. Everything else here — doors, hood, tailgate,
sunroof, headlamps — exists only in the wake payload, so it stays unknown until the
first "Refresh (wake car)" and then holds that value until the next wake. It is not
live state, and treating it as such would be misleading.
"""

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .const import CHARGING_ACTIVE, F_CHARGING_STAT, F_HEADLAMP
from .entity import KgmLinkDescribedEntity
from .status import is_open


@dataclass(frozen=True, kw_only=True)
class KgmBinary(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


def _opening(key: str, field: str, device_class: BinarySensorDeviceClass) -> KgmBinary:
    return KgmBinary(
        key=key,
        translation_key=key,
        device_class=device_class,
        value_fn=lambda s, f=field: is_open(s, f),
    )


BINARY_SENSORS: tuple[KgmBinary, ...] = (
    KgmBinary(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda s: s.get(F_CHARGING_STAT) in CHARGING_ACTIVE
        if s.get(F_CHARGING_STAT) is not None
        else None,
    ),
    _opening("door_driver", "drvtDoorOpndStat", BinarySensorDeviceClass.DOOR),
    _opening("door_passenger", "psstDoorOpndStat", BinarySensorDeviceClass.DOOR),
    _opening("door_rear_left", "rearLeftDoorOpndStat", BinarySensorDeviceClass.DOOR),
    _opening("door_rear_right", "rearRghtDoorOpndStat", BinarySensorDeviceClass.DOOR),
    _opening("tailgate", "tlgtOpndStat", BinarySensorDeviceClass.DOOR),
    _opening("hood", "hoodOpndStat", BinarySensorDeviceClass.DOOR),
    _opening("sunroof", "srfStat", BinarySensorDeviceClass.WINDOW),
    KgmBinary(
        key="headlamps",
        translation_key="headlamps",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda s: _headlamps_on(s),
    ),
)


def _headlamps_on(status: dict[str, Any]) -> bool | None:
    desc = str(status.get(f"{F_HEADLAMP}Desc") or "").strip().lower()
    if not desc:
        return None
    if "off" in desc:
        return False
    if "on" in desc:
        return True
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[KgmLinkBinarySensor] = []
    for coordinator in entry.runtime_data:
        entities.extend(KgmLinkBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)
    async_add_entities(entities)


class KgmLinkBinarySensor(KgmLinkDescribedEntity, BinarySensorEntity):
    entity_description: KgmBinary

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.status)
