"""HTTP client for the KGM Link API (plaintext-body path).

Auth envelope is signed but unencrypted (see crypto.py); bodies and responses are
plaintext JSON. Fresh EV status / location come via a two-step command flow:
`CmdEv(vehlId, pin) -> rctlMnId`, then poll `ResultEv(rctlMnId, vehlId)` until it lands.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientSession

from . import crypto
from .const import (
    BASE_URL_TEMPLATE,
    DEFAULT_REGION,
    EP_LOCATION_CMD,
    EP_LOCATION_RESULT,
    EP_CHANGE_DETAIL,
    EP_CHARGE_START,
    EP_CHARGE_STOP,
    EP_ENGINE_START_EV,
    EP_ENGINE_STOP_EV,
    EP_HVAC_STOP,
    EP_LAMP_HORN_OFF,
    EP_LAMP_HORN_ON,
    EP_LOGIN,
    EP_REMOTE_DOOR,
    EP_PUBLIC_KEY,
    EP_REFRESH_TOKEN,
    EP_STATUS_CMD_EV,
    EP_STATUS_RESULT_EV,
    EP_VEHICLE_FIX_DETAIL,
    EP_VEHICLES,
    F_AC_TEMPERATURE,
    F_CNNC_SCN,
    F_DEFROST_ON,
    F_EML,
    F_ENGINE_TIMEOUT,
    F_HVAC_ON,
    F_IS_DOOR_LOCK,
    F_LAMP,
    F_LAMP_HORN,
    F_PASSWORD,
    F_PIN,
    F_RCTL_MN_ID,
    F_REAR_HEAT_ON,
    F_REFRESH_TOKEN,
    F_TOKEN,
    F_VEHICLES,
    F_VEHL_ID,
    SEAT_FIELDS,
    RESULT_POLL_INTERVAL_S,
    RESULT_POLL_TIMEOUT_S,
)

_LOGGER = logging.getLogger(__name__)

# returnCode values seen from the server
_AUTH_CODES = {"20101", "20102", "20103"}   # token expired / invalid


class KgmLinkAuthError(Exception):
    """Credentials/refresh failed."""


class KgmLinkApiError(Exception):
    """Transport or server-side error."""

    def __init__(self, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.data = data or {}


class KgmLinkPinError(KgmLinkApiError):
    """Remote PIN rejected or locked."""


@dataclass(slots=True)
class KgmLinkClient:
    """Async client for one KGM Link account."""

    session: ClientSession
    region: str = DEFAULT_REGION
    pin: str | None = None
    # Held so an expired session can be recovered without user involvement — the
    # refresh token expires too, and then a fresh login is the only way back.
    email: str | None = None
    password: str | None = field(default=None, repr=False)
    _token: str | None = field(default=None, repr=False)
    _refresh_token: str | None = field(default=None, repr=False)
    _public_key: object | None = field(default=None, repr=False)
    # The server runs ONE remote command per account at a time ("previous command has
    # not ended yet"), so every car-touching call is serialised through this.
    _command_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def base_url(self) -> str:
        return BASE_URL_TEMPLATE.format(region=self.region)

    async def _ensure_key(self) -> None:
        if self._public_key is None:
            async with self.session.post(
                f"{self.base_url}{EP_PUBLIC_KEY}", data=b"",
                headers={"User-Agent": "Ccs/1.0.7.4 CFNetwork/3860.700.1 Darwin/25.6.0",
                         "Content-Type": "application/json"},
            ) as resp:
                data = await resp.json(content_type=None)
            self._public_key = crypto.load_public_key(data["PublicKey"])

    async def _send(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_key()
        headers = crypto.envelope_headers(self._public_key, token=self._token)
        async with self.session.post(
            f"{self.base_url}{path}", json=payload, headers=headers
        ) as resp:
            data = await resp.json(content_type=None)
        code = str(data.get("returnCode") or "")
        if resp.status == 401 or code in _AUTH_CODES:
            raise KgmLinkAuthError(f"{path}: {data.get('returnMessage')}")
        if code and code != "00000":
            raise KgmLinkApiError(f"{path} -> {code} {data.get('returnMessage')}")
        return data

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send, recovering the session once if the server rejects our token."""
        try:
            return await self._send(path, payload)
        except KgmLinkAuthError:
            if path in (EP_LOGIN, EP_REFRESH_TOKEN):
                raise
            await self._reauthenticate()
            return await self._send(path, payload)

    async def _reauthenticate(self) -> None:
        """Refresh the session, falling back to a full re-login.

        The refresh token expires as well ("Your session has expired. Please log in
        again."), and when it does, refreshing can never succeed — so retrying it
        forever would strand the config entry. Falling back to a login with the stored
        credentials lets the integration heal itself; only a genuinely bad credential
        gets as far as raising, which is what should trigger a reauth prompt.
        """
        if self._refresh_token:
            try:
                await self.async_refresh_token()
                return
            except KgmLinkAuthError as err:
                if not (self.email and self.password):
                    raise
                _LOGGER.debug("Refresh token rejected (%s); logging in again", err)
        elif not (self.email and self.password):
            raise KgmLinkAuthError("session expired and no credentials to log back in")
        await self.login(self.email, self.password)

    # --- session ------------------------------------------------------------
    async def login(self, email: str, password: str) -> dict[str, Any]:
        data = await self._send(
            EP_LOGIN, {F_EML: email, F_PASSWORD: password, F_CNNC_SCN: "1"}
        )
        self._store_tokens(data)
        return data

    async def async_refresh_token(self) -> None:
        data = await self._send(EP_REFRESH_TOKEN, {F_REFRESH_TOKEN: self._refresh_token})
        self._store_tokens(data)

    def _store_tokens(self, data: dict[str, Any]) -> None:
        token = data.get(F_TOKEN)
        if not token:
            raise KgmLinkAuthError("no token in response")
        self._token = token
        self._refresh_token = data.get(F_REFRESH_TOKEN) or self._refresh_token

    # --- vehicles -----------------------------------------------------------
    async def async_get_vehicles(self) -> list[dict[str, Any]]:
        data = await self._post(EP_VEHICLES, {})
        return data.get(F_VEHICLES, [])

    async def async_get_vehicle_detail(self, vehicle_id: int) -> dict[str, Any]:
        return await self._post(EP_VEHICLE_FIX_DETAIL, {F_VEHL_ID: vehicle_id})

    async def async_read_cached(self, vehicle_id: int) -> dict[str, Any]:
        """Cached status (SoC/range/charging) — no PIN, no wake. Safe to poll often."""
        return await self._post(EP_CHANGE_DETAIL, {F_VEHL_ID: vehicle_id})

    # --- EV status (wake + poll) -------------------------------------------
    async def async_refresh_status(self, vehicle_id: int) -> dict[str, Any]:
        """Wake the car and poll until fresh telemetry lands. Requires the PIN."""
        return await self._cmd_then_poll(
            EP_STATUS_CMD_EV, EP_STATUS_RESULT_EV,
            {F_VEHL_ID: vehicle_id, "pin": self._require_pin()}, vehicle_id,
        )

    async def async_refresh_location(self, vehicle_id: int) -> dict[str, Any]:
        return await self._cmd_then_poll(
            EP_LOCATION_CMD, EP_LOCATION_RESULT,
            {F_VEHL_ID: vehicle_id, "pin": self._require_pin(),
             "userLatitude": 0, "userLongitude": 0}, vehicle_id,
        )

    def _require_pin(self) -> str:
        if not self.pin:
            raise KgmLinkPinError("remote PIN not configured")
        return self.pin

    async def _cmd_then_poll(
        self, cmd_ep: str, result_ep: str, cmd_body: dict[str, Any], vehicle_id: int
    ) -> dict[str, Any]:
        async with self._command_lock:
            return await self._cmd_then_poll_locked(cmd_ep, result_ep, cmd_body, vehicle_id)

    async def _cmd_then_poll_locked(
        self, cmd_ep: str, result_ep: str, cmd_body: dict[str, Any], vehicle_id: int
    ) -> dict[str, Any]:
        cmd = await self._post(cmd_ep, cmd_body)
        if cmd.get("isPinLocked"):
            raise KgmLinkPinError("remote PIN is locked")
        rctl = cmd.get(F_RCTL_MN_ID)
        if rctl is None:
            raise KgmLinkApiError(f"{cmd_ep}: {cmd.get('errorMessage')} (no rctlMnId)")

        poll_body = {F_RCTL_MN_ID: rctl, F_VEHL_ID: vehicle_id}
        deadline = asyncio.get_running_loop().time() + RESULT_POLL_TIMEOUT_S
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(RESULT_POLL_INTERVAL_S)
            try:
                result = await self._post(result_ep, poll_body)
            except KgmLinkApiError as err:
                # "still processing" style codes -> keep polling
                if "20214" in str(err) or "processing" in str(err).lower():
                    continue
                raise
            if not result.get("retryFlag", False):
                return result
        raise KgmLinkApiError(f"{result_ep}: timed out waiting for result")

    # --- remote commands ----------------------------------------------------
    # These ACTUATE the car. Every one takes the remote PIN, and the server runs
    # only one remote command at a time. Results are NOT pollable — the app gets
    # them by Firebase push (research/PROTOCOL.md §7.3) — so a successful return
    # here means "the server accepted the command", not "the car did it".
    #
    # The key names below are the wire names the server actually asks for, which are
    # NOT the Swift property names in the binary (research/PROTOCOL.md §7.2). Anything
    # still marked UNVERIFIED in const.py will be rejected with "10001 <real> is
    # required" until research/probe_commands.py recovers it.

    async def _remote(self, path: str, vehicle_id: int, **extra: Any) -> dict[str, Any]:
        body = {F_VEHL_ID: int(vehicle_id), F_PIN: self._require_pin(), **extra}
        async with self._command_lock:
            data = await self._post(path, body)
        if data.get("isPinLocked"):
            raise KgmLinkPinError("remote PIN is locked")
        if data.get("errorCode"):
            raise KgmLinkApiError(
                f"{path} -> {data['errorCode']} {data.get('errorMessage')}", data
            )
        return data

    async def async_set_door_lock(self, vehicle_id: int, lock: bool) -> dict[str, Any]:
        """Lock (True) or unlock (False) the doors."""
        return await self._remote(EP_REMOTE_DOOR, vehicle_id=vehicle_id, **{F_IS_DOOR_LOCK: lock})

    async def async_set_charging(self, vehicle_id: int, charge: bool) -> dict[str, Any]:
        """Start or cancel charging immediately."""
        return await self._remote(
            EP_CHARGE_START if charge else EP_CHARGE_STOP, vehicle_id=vehicle_id
        )

    async def async_start_climate(
        self,
        vehicle_id: int,
        *,
        temperature: float,
        duration: int,
        hvac_on: bool = True,
        defrost: bool = False,
        rear_window_heat: bool = False,
        seats: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Precondition the cabin. The car stops on its own after `duration` minutes."""
        seats = seats or {}
        return await self._remote(
            EP_ENGINE_START_EV,
            vehicle_id=vehicle_id,
            **{
                F_HVAC_ON: hvac_on,
                F_DEFROST_ON: defrost,
                F_REAR_HEAT_ON: rear_window_heat,
                F_AC_TEMPERATURE: float(temperature),
                F_ENGINE_TIMEOUT: int(duration),
                **{seat: int(seats.get(seat, 0)) for seat in SEAT_FIELDS},
            },
        )

    async def async_stop_climate(self, vehicle_id: int) -> dict[str, Any]:
        """Stop preconditioning.

        RemoteHvacStop is the climate-only stop; RemoteEngineStopEv shuts the whole
        remote session down. Try the former and fall back, since which one a given
        vehicle accepts is not something the binary tells us.

        The fallback is skipped whenever the first rejection looks like a PIN problem.
        The remote PIN locks out after a handful of wrong attempts, and spending two of
        them on one button press is not a trade worth making.
        """
        try:
            return await self._remote(EP_HVAC_STOP, vehicle_id=vehicle_id)
        except KgmLinkPinError:
            raise
        except KgmLinkApiError as err:
            if err.data.get("failCount"):
                raise
            _LOGGER.debug("RemoteHvacStop rejected (%s); trying RemoteEngineStopEv", err)
            return await self._remote(EP_ENGINE_STOP_EV, vehicle_id=vehicle_id)

    async def async_set_lamp_horn(
        self, vehicle_id: int, *, lamp: bool = True, horn: bool = False
    ) -> dict[str, Any]:
        """Flash the lights and/or sound the horn. Both False turns them back off."""
        if not lamp and not horn:
            return await self._remote(EP_LAMP_HORN_OFF, vehicle_id=vehicle_id)
        return await self._remote(
            EP_LAMP_HORN_ON, vehicle_id=vehicle_id, **{F_LAMP: lamp, F_LAMP_HORN: horn}
        )
