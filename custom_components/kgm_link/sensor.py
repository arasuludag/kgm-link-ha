"""KGM Link sensors — EV battery, range, charging, odometer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from datetime import datetime

from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import KgmLinkConfigEntry
from .const import (
    CHARGING_ACTIVE,
    CHARGING_STATES,
    DOMAIN,
    F_CHARGE_80_H,
    F_CHARGE_80_M,
    F_CHARGE_FULL_H,
    F_CHARGE_FULL_M,
    F_CHARGING_STAT,
    F_ODOMETER_CACHED,
    F_RANGE_CACHED,
    F_SOC,
    F_UPDATED,
)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    dt = dt_util.parse_datetime(str(value))
    return dt_util.as_local(dt) if dt and dt.tzinfo is None else dt


def _is_charging(status: dict[str, Any]) -> bool:
    return status.get(F_CHARGING_STAT) in CHARGING_ACTIVE


def _charge_mins(status: dict[str, Any], h_key: str, m_key: str) -> int | None:
    # The API returns a placeholder (both timers equal) when not charging.
    if not _is_charging(status):
        return None
    return _mins(status, h_key, m_key)


def _mins(status: dict[str, Any], h_key: str, m_key: str) -> int | None:
    h, m = status.get(h_key), status.get(m_key)
    if h is None and m is None:
        return None
    return (h or 0) * 60 + (m or 0)


@dataclass(frozen=True, kw_only=True)
class KgmSensor(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[KgmSensor, ...] = (
    KgmSensor(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get(F_SOC),
    ),
    KgmSensor(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get(F_RANGE_CACHED),
    ),
    KgmSensor(
        key="charging_status",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        options=["charging", "not_charging", "unknown"],
        value_fn=lambda s: CHARGING_STATES.get(s.get(F_CHARGING_STAT), "unknown"),
    ),
    KgmSensor(
        key="time_to_full",
        translation_key="time_to_full",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda s: _charge_mins(s, F_CHARGE_FULL_H, F_CHARGE_FULL_M),
    ),
    KgmSensor(
        key="time_to_80",
        translation_key="time_to_80",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda s: _charge_mins(s, F_CHARGE_80_H, F_CHARGE_80_M),
    ),
    KgmSensor(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.get(F_ODOMETER_CACHED),
    ),
    KgmSensor(
        key="last_updated",
        translation_key="last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: _parse_dt(s.get(F_UPDATED)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[KgmLinkSensor] = []
    for coordinator in entry.runtime_data:
        entities.extend(KgmLinkSensor(coordinator, desc) for desc in SENSORS)
    async_add_entities(entities)


class KgmLinkSensor(CoordinatorEntity, SensorEntity):
    entity_description: KgmSensor
    _attr_has_entity_name = True

    def __init__(self, coordinator, description: KgmSensor) -> None:
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
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})
