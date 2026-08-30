"""Every remote command body, checked against the schemas in research/PROTOCOL.md §7.

These schemas came out of the app binary's Swift reflection metadata rather than a
packet capture, so this file is the guard against a typo in a field name silently
producing a command the car ignores. Field names are spelled out literally on purpose —
asserting against the same constants the code uses would prove nothing.
"""

from __future__ import annotations

import asyncio

import conftest  # noqa: F401  (installs the import stubs)
import pytest

from kgm import api, const


class RecordingClient(api.KgmLinkClient):
    """A client that records what it would have sent instead of sending it."""

    def __init__(self, response=None, **kwargs):
        super().__init__(**kwargs)
        self.sent: list[tuple[str, dict]] = []
        self._response = response or {}

    async def _post(self, path, payload):
        self.sent.append((path, payload))
        return self._response


def send(coro_factory, pin="1234", response=None):
    """Run one command and return the (path, body) it produced."""
    client = RecordingClient(response=response, session=None, pin=pin)
    asyncio.run(coro_factory(client))
    return client.sent[0]


def test_door_lock_body():
    path, body = send(lambda c: c.async_set_door_lock(42, True))
    assert path == "/Customer/V1/RemoteDoor"
    assert body == {"vehicleId": 42, "pin": "1234", "isDoorLock": True}


def test_unlock_flips_the_flag():
    _, body = send(lambda c: c.async_set_door_lock(42, False))
    assert body["isDoorLock"] is False


def test_remote_commands_use_vehicleid_not_vehlid():
    """The status endpoints use `vehlId`; the remote ones use `vehicleId`."""
    _, body = send(lambda c: c.async_set_door_lock(42, True))
    assert "vehicleId" in body
    assert "vehlId" not in body


def test_charge_start_and_stop_are_different_endpoints():
    start, _ = send(lambda c: c.async_set_charging(42, True))
    stop, body = send(lambda c: c.async_set_charging(42, False))
    assert start == "/Customer/V1/ImmediateChargeStartCmd"
    assert stop == "/Customer/V1/ImmediateChargeCancelCmd"
    assert body == {"vehicleId": 42, "pin": "1234"}


def test_climate_start_body():
    path, body = send(
        lambda c: c.async_start_climate(
            42,
            temperature=21.5,
            duration=10,
            defrost=True,
            rear_window_heat=False,
            seats={"driveSeat": 3},
        )
    )
    assert path == "/Customer/V1/RemoteEngineStartEv"
    assert body == {
        "vehicleId": 42,
        "pin": "1234",
        "hvacOn": True,
        "defrostOn": True,
        "rearWindowHeatOn": False,
        "acTemperature": 21.5,
        "timeoutToTurnOffEngine": 10,
        "driveSeat": 3,
        "passengerSeat": 0,
        "secondLeftSeat": 0,
        "secondRightSeat": 0,
        "thirdLeftSeat": 0,
        "thirdRightSeat": 0,
    }


def test_climate_start_always_sends_every_seat():
    """The struct has no optional seats — omitting one risks a rejected body."""
    _, body = send(lambda c: c.async_start_climate(42, temperature=20, duration=5))
    assert sorted(k for k in body if k.endswith("Seat")) == sorted(const.SEAT_FIELDS)
    assert all(body[seat] == 0 for seat in const.SEAT_FIELDS)


def test_lamp_horn_on_and_off():
    path, body = send(lambda c: c.async_set_lamp_horn(42, lamp=True, horn=False))
    assert path == "/Customer/V1/RemoteLampHornOn"
    assert body == {"vehicleId": 42, "pin": "1234", "lamp": True, "lampHorn": False}

    path, body = send(lambda c: c.async_set_lamp_horn(42, lamp=False, horn=False))
    assert path == "/Customer/V1/RemoteLampHornOff"
    assert body == {"vehicleId": 42, "pin": "1234"}


def test_no_pin_is_refused_before_anything_is_sent():
    with pytest.raises(api.KgmLinkPinError):
        send(lambda c: c.async_set_door_lock(42, True), pin=None)


def test_locked_pin_is_reported_not_retried():
    """The PIN has a lockout — a locked PIN must surface, never be hammered."""
    with pytest.raises(api.KgmLinkPinError):
        send(lambda c: c.async_set_door_lock(42, True), response={"isPinLocked": True})


def test_server_error_code_becomes_an_exception():
    with pytest.raises(api.KgmLinkApiError, match="20501"):
        send(
            lambda c: c.async_set_charging(42, True),
            response={"errorCode": "20501", "errorMessage": "previous command has not ended yet"},
        )


def test_commands_never_overlap():
    """The server runs one remote command at a time, so the client must serialise."""
    order: list[str] = []

    class SlowClient(RecordingClient):
        async def _post(self, path, payload):
            name = path.rsplit("/", 1)[-1]
            order.append(f"start {name}")
            await asyncio.sleep(0.02)
            order.append(f"end {name}")
            return {}

    async def both():
        client = SlowClient(session=None, pin="1234")
        await asyncio.gather(
            client.async_set_door_lock(1, True),
            client.async_set_charging(1, True),
        )

    asyncio.run(both())
    assert not any(
        order[i].startswith("start") and order[i + 1].startswith("start")
        for i in range(len(order) - 1)
    ), f"commands overlapped: {order}"


def test_seat_levels_are_symmetric_around_off():
    """SeatLevelValue runs cool_high..nope..heat_high, so off has to be the zero point."""
    assert const.SEAT_LEVELS["off"] == 0
    assert const.SEAT_LEVELS["cool_high"] == -const.SEAT_LEVELS["heat_high"]
    assert set(const.SEAT_LEVEL_OPTIONS) == set(const.SEAT_LEVELS)


def test_climate_duration_matches_the_app_cap():
    assert const.MAX_CLIMATE_DURATION == 10
    assert const.MIN_CLIMATE_DURATION >= 1


def test_climate_stop_falls_back_to_the_engine_endpoint():
    """Which stop endpoint a vehicle accepts is not knowable ahead of time."""
    tried: list[str] = []

    class Rejecting(RecordingClient):
        async def _post(self, path, payload):
            tried.append(path)
            if path == "/Customer/V1/RemoteHvacStop":
                return {"errorCode": "20999", "errorMessage": "not supported"}
            return {}

    asyncio.run(Rejecting(session=None, pin="1234").async_stop_climate(42))
    assert tried == ["/Customer/V1/RemoteHvacStop", "/Customer/V1/RemoteEngineStopEv"]


def test_climate_stop_does_not_spend_a_second_pin_attempt():
    """The remote PIN locks out — one button press must cost at most one attempt."""
    tried: list[str] = []

    class BadPin(RecordingClient):
        async def _post(self, path, payload):
            tried.append(path)
            return {"errorCode": "20401", "errorMessage": "invalid pin", "failCount": 1}

    with pytest.raises(api.KgmLinkApiError):
        asyncio.run(BadPin(session=None, pin="0000").async_stop_climate(42))
    assert tried == ["/Customer/V1/RemoteHvacStop"], f"retried after a PIN failure: {tried}"
