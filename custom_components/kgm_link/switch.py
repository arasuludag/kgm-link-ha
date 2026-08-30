"""KGM Link switches.

Two kinds live here. The charge switch is a real control: it goes straight to the car,
independent of the EVSE, and its state comes from the free cached poll. Defrost and
rear-window heat are not controls at all — they stage options for the *next* climate
start, since the API only accepts them as part of that one-shot payload.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .const import CHARGING_ACTIVE, CHARGING_STATE_CHARGING, CHARGING_STATE_NOT_CHARGING, F_CHARGING_STAT
from .coordinator import KgmLinkCoordinator
from .entity import KgmLinkEntity, KgmLinkSettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[SwitchEntity] = []
    for coordinator in entry.runtime_data:
        entities.append(KgmLinkChargeSwitch(coordinator))
        entities.append(KgmLinkClimateOption(coordinator, "defrost"))
        entities.append(KgmLinkClimateOption(coordinator, "rear_window_heat"))
    async_add_entities(entities)


class KgmLinkChargeSwitch(KgmLinkEntity, SwitchEntity):
    _attr_translation_key = "charge"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: KgmLinkCoordinator) -> None:
        super().__init__(coordinator, "charge")

    @property
    def is_on(self) -> bool | None:
        state = self.status.get(F_CHARGING_STAT)
        return state in CHARGING_ACTIVE if state is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, charge: bool) -> None:
        await self.coordinator.async_command(
            lambda: self.coordinator.client.async_set_charging(
                self.coordinator.vehicle_id, charge
            ),
            # Not persisted: the cached poll reports charging state, so let it correct us.
            optimistic={
                F_CHARGING_STAT: CHARGING_STATE_CHARGING
                if charge
                else CHARGING_STATE_NOT_CHARGING
            },
        )


class KgmLinkClimateOption(KgmLinkSettingEntity, SwitchEntity):
    """Defrost / rear-window heat, applied on the next climate start."""

    def __init__(self, coordinator: KgmLinkCoordinator, setting: str) -> None:
        super().__init__(coordinator, setting)
        self._setting = setting
        self._attr_translation_key = setting

    @property
    def is_on(self) -> bool:
        return getattr(self.coordinator.climate_settings, self._setting)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set(False)

    def _set(self, value: bool) -> None:
        setattr(self.coordinator.climate_settings, self._setting, value)
        self.async_write_ha_state()

    def restore(self, value: str) -> None:
        setattr(self.coordinator.climate_settings, self._setting, value == STATE_ON)
