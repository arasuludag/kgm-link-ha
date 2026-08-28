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
    EP_LOGIN,
    EP_PUBLIC_KEY,
    EP_REFRESH_TOKEN,
    EP_STATUS_CMD_EV,
    EP_STATUS_RESULT_EV,
    EP_VEHICLE_FIX_DETAIL,
    EP_VEHICLES,
    F_CNNC_SCN,
    F_EML,
    F_PASSWORD,
    F_RCTL_MN_ID,
    F_REFRESH_TOKEN,
    F_TOKEN,
    F_VEHICLES,
    F_VEHL_ID,
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


class KgmLinkPinError(KgmLinkApiError):
    """Remote PIN rejected or locked."""


@dataclass(slots=True)
class KgmLinkClient:
    """Async client for one KGM Link account."""

    session: ClientSession
    region: str = DEFAULT_REGION
    pin: str | None = None
    _token: str | None = field(default=None, repr=False)
    _refresh_token: str | None = field(default=None, repr=False)
    _public_key: object | None = field(default=None, repr=False)

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
        """Send with automatic 401 -> RefreshToken -> retry-once."""
        try:
            return await self._send(path, payload)
        except KgmLinkAuthError:
            if path in (EP_LOGIN, EP_REFRESH_TOKEN) or not self._refresh_token:
                raise
            await self.async_refresh_token()
            return await self._send(path, payload)

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
