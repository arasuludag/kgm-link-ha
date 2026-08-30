"""The car reports door/lock state as a server-rendered English string."""

from __future__ import annotations

import conftest  # noqa: F401  (installs the import stubs)

from kgm import status


def test_locked_and_unlocked_are_distinguished():
    # "Unlocked" contains "locked", so the negative has to be checked first.
    assert status.is_locked({"drvtDoorStatDesc": "Locked"}, "drvtDoorStat") is True
    assert status.is_locked({"drvtDoorStatDesc": "Unlocked"}, "drvtDoorStat") is False
    assert status.is_locked({"drvtDoorStatDesc": "UNLOCKED"}, "drvtDoorStat") is False


def test_open_and_closed_are_distinguished():
    assert status.is_open({"hoodOpndStatDesc": "Open"}, "hoodOpndStat") is True
    assert status.is_open({"hoodOpndStatDesc": "Closed"}, "hoodOpndStat") is False


def test_unknown_rather_than_guessed():
    """No description means unknown — never a guess at the undocumented integer.

    A confidently wrong lock state is worse than an absent one.
    """
    assert status.is_locked({}, "drvtDoorStat") is None
    assert status.is_locked({"drvtDoorStatDesc": ""}, "drvtDoorStat") is None
    assert status.is_locked({"drvtDoorStat": 1}, "drvtDoorStat") is None
    assert status.is_open({"hoodOpndStatDesc": "N/A"}, "hoodOpndStat") is None
