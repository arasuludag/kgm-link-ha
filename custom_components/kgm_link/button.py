"""KGM Link buttons — on-demand wake actions (these wake the car; need the PIN)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .coordinator import KgmLinkCoordinator
from .entity import KgmLinkDescribedEntity


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
    # Find-my-car: flashing the lights is the harmless one, so it is the default;
    # the horn is separate because it is not something to press by accident.
    KgmButton(
        key="flash_lights",
        translation_key="flash_lights",
        press_fn=lambda c: c.async_command(
            lambda: c.client.async_set_lamp_horn(c.vehicle_id, lamp=True, horn=False)
        ),
    ),
    KgmButton(
        key="horn_and_lights",
        translation_key="horn_and_lights",
        entity_registry_enabled_default=False,
        press_fn=lambda c: c.async_command(
            lambda: c.client.async_set_lamp_horn(c.vehicle_id, lamp=True, horn=True)
        ),
    ),
    KgmButton(
        key="lights_off",
        translation_key="lights_off",
        press_fn=lambda c: c.async_command(
            lambda: c.client.async_set_lamp_horn(c.vehicle_id, lamp=False, horn=False)
        ),
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


class KgmLinkButton(KgmLinkDescribedEntity, ButtonEntity):
    entity_description: KgmButton

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)
