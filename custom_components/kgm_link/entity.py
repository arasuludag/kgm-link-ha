"""Shared base for every KGM Link entity."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KgmLinkCoordinator


class KgmLinkEntity(CoordinatorEntity[KgmLinkCoordinator]):
    """One entity belonging to one vehicle."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KgmLinkCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vehicle_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.vehicle_id))},
            manufacturer="KG Mobility",
            name=coordinator.device_name,
            model=coordinator.model,
            serial_number=coordinator.vin,
        )

    @property
    def status(self) -> dict[str, Any]:
        return self.coordinator.data or {}


class KgmLinkDescribedEntity(KgmLinkEntity):
    """A KGM Link entity driven by an EntityDescription."""

    def __init__(
        self, coordinator: KgmLinkCoordinator, description: EntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description


class KgmLinkSettingEntity(KgmLinkEntity, RestoreEntity):
    """A control that only stages part of the next climate command.

    Nothing here is read back from the car — the API has no endpoint that reports what
    preconditioning is configured — so these restore their own last value across a
    restart and write it into the coordinator's climate settings.
    """

    _attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self.restore(last.state)

    def restore(self, value: str) -> None:
        """Apply a restored state string to the coordinator's climate settings."""
        raise NotImplementedError
