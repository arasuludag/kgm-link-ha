"""KGM Link buttons — on-demand wake actions (these wake the car; need the PIN)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .const import DOMAIN
from .coordinator import KgmLinkCoordinator


@dataclass(frozen=True, kw_only=True)
class KgmButton(ButtonEntityDescription):
    press_fn: Callable[[KgmLinkCoordinator], Coroutine[Any, Any, None]]


BUTTONS: tuple[KgmButton, ...] = (
    KgmButton(
        key="locate",
        translation_key="locate",
        press_fn=lambda c: c.async_locate(),
    ),
    KgmButton(
        key="refresh",
        translation_key="refresh",
        press_fn=lambda c: c.async_wake_refresh(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[KgmLinkButton] = []
    for coordinator in entry.runtime_data:
        entities.extend(KgmLinkButton(coordinator, desc) for desc in BUTTONS)
    async_add_entities(entities)


class KgmLinkButton(ButtonEntity):
    entity_description: KgmButton
    _attr_has_entity_name = True

    def __init__(self, coordinator: KgmLinkCoordinator, description: KgmButton) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.vehicle_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.vehicle_id))},
            manufacturer="KG Mobility",
            name=coordinator.device_name,
            model=coordinator.model,
            serial_number=coordinator.vin,
        )

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)
