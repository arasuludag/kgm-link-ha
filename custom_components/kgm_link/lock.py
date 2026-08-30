"""KGM Link door lock.

The lock command is fire-and-forget: the car reports the outcome by push, which HA
never sees, and the cached poll does not carry lock state at all. So the state shown
here is whatever the last wake read (or the last command) said. Press "Refresh (wake
car)" for the truth.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KgmLinkConfigEntry
from .coordinator import KgmLinkCoordinator
from .entity import KgmLinkEntity
from .status import is_locked

# The driver's door is what the app treats as "the" lock state.
LOCK_FIELD = "drvtDoorStat"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KgmLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(KgmLinkLock(c) for c in entry.runtime_data)


class KgmLinkLock(KgmLinkEntity, LockEntity):
    _attr_translation_key = "doors"
    # The state here is only ever as fresh as the last wake, so HA should offer both
    # buttons rather than hiding one behind a state it cannot trust.
    _attr_assumed_state = True

    def __init__(self, coordinator: KgmLinkCoordinator) -> None:
        super().__init__(coordinator, "door_lock")

    @property
    def is_locked(self) -> bool | None:
        return is_locked(self.status, LOCK_FIELD)

    async def async_lock(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, lock: bool) -> None:
        await self.coordinator.async_command(
            lambda: self.coordinator.client.async_set_door_lock(
                self.coordinator.vehicle_id, lock
            ),
            optimistic={f"{LOCK_FIELD}Desc": "Locked" if lock else "Unlocked"},
            persist=True,
        )
