"""Reading the vehicle's door / lock / open states.

The wake payload (`VehicleStatusCheckResultEv`) reports every one of these twice: an
undocumented integer (`drvtDoorStat`) and a server-rendered English string
(`drvtDoorStatDesc`). We trust the string. The integer encodings appear nowhere in the
app binary, and a confidently-wrong lock state is worse than an unknown one — so when
there is no description, these return None rather than guess.
"""

from __future__ import annotations

from typing import Any

# Checked in order: the "false" words are tested first because "unlocked" also
# contains "locked".
_UNLOCKED = ("unlock",)
_LOCKED = ("locked",)
_CLOSED = ("close", "shut")
_OPEN = ("open",)


def _match(desc: Any, true_words: tuple[str, ...], false_words: tuple[str, ...]) -> bool | None:
    text = str(desc or "").strip().lower()
    if not text:
        return None
    if any(word in text for word in false_words):
        return False
    if any(word in text for word in true_words):
        return True
    return None


def is_locked(status: dict[str, Any], field: str) -> bool | None:
    """True if `field` (e.g. "drvtDoorStat") reports a locked door."""
    return _match(status.get(f"{field}Desc"), _LOCKED, _UNLOCKED)


def is_open(status: dict[str, Any], field: str) -> bool | None:
    """True if `field` (e.g. "hoodOpndStat") reports something standing open."""
    return _match(status.get(f"{field}Desc"), _OPEN, _CLOSED)
