# KGM Link API — Protocol Notes

Reverse-engineering record for the `tr-open-api.kgm-link.com` API used by the
**KGM LINK** iOS app (bundle `com.kgm.link.turkey`, app version `1.0.7.4`,
process name `Ccs`). Turkey region host prefix is `tr-`; other regions likely
mirror the path structure on a different host.

**No secrets in this file.** Header names, byte sizes, and algorithms only — never
captured nonces, signatures, tokens, keys, or personal identifiers.

---

## 1. Transport envelope (VERIFIED against the live server)

### 1.1 Session key
```
K = SecRandomCopyBytes(32);  S = uppercase_hex(K)   # 64-char hex string ("the session key")
```

### 1.2 Server public key — FETCHED (not embedded)
`POST /Common/V1/PublicKey` (unauth, no envelope) -> `{"PublicKey":"<b64 SPKI DER>"}`, an
RSA-2048 key, cached by `TwoWayCryptoManager.fetchPublicKey()`. Can rotate / is region-
specific, so the client fetches it. (The 4 RSA keys first carved from the binary were the
EC digital-key certs, unrelated.)

### 1.3 Envelope — CONFIRMED LIVE (server accepts RSA + HMAC)
```
X-Timestamp = ISO8601 UTC  "yyyy-MM-dd'T'HH:mm:ss'Z'"
X-Nonce     = base64( RSA-2048 PKCS#1 v1.5 ( S.utf8 ) )   # plaintext is S — proven: sending K -> "HMAC failed"
X-Signature = base64( HMAC-SHA256( key=S.utf8, msg=(X-Timestamp + X-Nonce + S).utf8 ) )
+ X-Encrypted:True · IsMobile:True · LangCode:en · Offset:<tz> · Authorization: Bearer <HS256 JWT>
```
Server error codes seen (unencrypted) while probing: `20906 RSA decryption failed`,
`20909 HMAC signature verification failed`. Once both pass the server replies with an
**encrypted** body — proving the envelope is accepted.

### 1.3b THE BYPASS — plaintext bodies (this is what the integration uses)
The body cipher is **not needed**. Send `X-Encrypted: False` with a **plaintext JSON body**
and the server accepts it (the signature covers only `ts+nonce+S`, not the body). Responses
come back as plaintext JSON. Confirmed end-to-end: login, vehicle list, and EV status all work
this way. `makeKeyAndIV` (below) is documented only for completeness.

### 1.4 Body cipher — static secret RECOVERED; KDF shape mapped; exact bytes need a hook
Bodies are **AES-CBC** (80-byte error responses are 5x16), key+IV from
`TwoWayCryptoManager.makeKeyAndIV(key: S)`. Disassembly of `func_100024104`:
```
guard S.count >= 40
arr30 = func_1000238a0()                 # 30-element STATIC array of Swift string fragments
                                         #   (relative-ptr descriptors @ 0x1010395a8)
combined = func_100023c04(arr30, S)      # generic combine of the static array with S
p0 = combined[range0]; p1 = combined[range1]; p2 = combined[range2]   # 3 fixed-range slices
                                         #   bounds seen: 10, 20, 30; Range consts @ 0x101039580/590
built = p0 + p1 + p2                     # append into one hex string
raw   = hexDecode(built)                 # func_100023cc8 ("hex to binary fail")
material = SHA256(raw)                    # CryptoSwift Array<UInt8>.sha256()  -> 32 bytes
# key (32) + iv (16) derived from `material` / `raw`
```
Static secret (recovered, but the integration does not use it — the plaintext bypass
makes it unnecessary): the Info.plist `ENCRYPTED_SECRET_KEY` XOR'd with the bundle id
(repeating), then hex-decoded, yields a 32-byte AES key; `IV_VALUE` deobfuscates the same
way. The literal value is withheld from this repo — it is the vendor's key and is not
needed here.

UNRESOLVED: the 30-element static array's contents + the exact combine/slice order. ~400
brute-force key derivations (S, secret, and combinations) all failed against a known-plaintext
oracle. This is deliberately layered obfuscation; the reliable finish is a **runtime hook** of
`makeKeyAndIV` (Ccs + 0x24104) or CommonCrypto `CCCrypt` to dump the 32-byte key + 16-byte IV
for a known `S` (blocked here by macOS SIP on the hardened app).

## 2. Observed endpoints (base `https://tr-open-api.kgm-link.com`)

Login / account:
- `POST /Customer/V1/Login` — credentials in body → returns JWT + profile
- `POST /Customer/V1/Vehicles` — vehicle list
- `POST /Customer/V1/VehiclesChangeDetail`
- `POST /Customer/V1/VehiclesFixDetail` — static vehicle detail (largish)
- `POST /Customer/V1/VehicleRemoteGroup`
- `POST /Customer/V1/NoticesForApp`
- `POST /Customer/V1/GetImageContents` — vehicle render PNG (huge; skip in HA)
- `POST /DigitalKey/V1/VehicleDetails`
- `POST /Common/V1/BannerImages`

EV status (the important loop):
- `POST /Customer/V1/VehicleStatusCheckCmdEv` — **wakes the car** / requests a fresh
  telemetry pull (small resp, ~216 B → a job/ticket)
- `POST /Customer/V1/VehicleStatusCheckResultEv` — **polled** every ~3–4 s until the
  result is fresh (resp grows 1344 B → 1772 B when the real payload lands)

### Status poll pattern (from capture, 14:47:45 → 14:48:02)
```
CmdEv                -> 216 B   (issue wake/refresh)
ResultEv  (t+3s)     -> 1344 B  (pending)
ResultEv  (t+6s)     -> 1344 B  (pending)
ResultEv  (t+9s)     -> 1344 B  (pending)
ResultEv  (t+12s)    -> 1344 B  (pending)
ResultEv  (t+16s)    -> 1772 B  (fresh telemetry)
```

### HA polling strategy implication
`CmdEv` wakes the car — cheap for the app, expensive for the 12 V battery if HA
does it on a tight schedule. The coordinator MUST distinguish:
- **passive read** — call `ResultEv` only (last cached telemetry, no wake), for the
  frequent poll.
- **active refresh** — `CmdEv` + poll `ResultEv`, only on explicit user request or a
  slow cadence, ideally gated on charging/ignition state.

---

## 3. Response schemas

Unknown until the envelope is decrypted. Fill per endpoint here once `crypto.py`
can round-trip. Do not paste decrypted bodies containing VIN / account id / location.

## 4. Reproduction

Bundle inspected at `/Applications/KGM LINK.app/Wrapper/Ccs.app` (iOS-on-Mac build).
Capture via Proxyman with the cert trusted on macOS; filter process `Ccs`.
`NSAllowsArbitraryLoads=true`, no TrustKit/pinning → MITM works without patching.

---

## 5. API surface & scope (from binary data models)

### Multiple vehicles — YES
`/Customer/V1/Vehicles` returns `vehicleList`; each item has `vehicleId`, `nickname`,
`modelName`, `vin`, `isDefault`. The app is multi-car (a default vehicle + a picker).
The integration creates **one HA device per vehicle** (coordinator per `vehicleId`),
named by `nickname`, with `modelName` as model and `vin` as serial.

### EV status models (response fields to map once decrypted)
`EvBattRsoc` (state of charge %), `BatteryChargingStatus`, `BatteryState`, `BatteryUsage`,
`DrivingSummary*`, `DrivingInfo*`. These live in the `VehicleStatusCheckResultEv` payload.

### Remote commands (present, not yet wired)
`RemoteDoorLockBody` (lock/unlock), `RemoteCharge` + `ChargeAction` (start/stop charge),
`RemoteEngineStartEv`/`RemoteEngineStopEv` + `RemoteHvacStop` (climate/precondition),
`RemoteLampHornOn`/`Off`. Paths are built in-app — capture each action once to confirm
its endpoint, then expose as HA lock/switch/button.

### Vehicle location — RESOLVED (separate endpoint pair)
Car location is its own Cmd/poll-Result pair, same shape as EV status:
`/Customer/V1/LocationFinderCmd` (wakes/locates, ~216 B) then
`/Customer/V1/LocationFinderResult` polled ~3 s until the fix lands (280 B pending ->
300 B fresh). Same envelope + Bearer. Exposed as a HA `device_tracker`. Passive
`LocationFinderResult` returns last-known position without waking the car.

### Session / token refresh
`/Customer/V1/RefreshToken` (Bearer + refresh token in the encrypted body) returns a new
JWT (~2156 B, like Login). Observed flow on token expiry:
`request -> 401 -> RefreshToken -> retry -> 200`. The client implements
401 -> refresh -> retry-once (except on Login/RefreshToken themselves).

### Regions — only `tr`
This app ships `tr-open-api.kgm-link.com` (prod) and `dev-open-api...` (staging) only.
Other countries are separate apps with their own host **and their own embedded server
RSA key**, so only `tr` can be verified here. Region is a config option defaulting to
`tr`; supporting another region means contributing that region's host + public key,
extracted from that region's app the same way (`research/keys/`).


---

## 6. Plaintext schemas (discovered live)

All POST, `X-Encrypted: False`, signed envelope. Auth endpoints need `Authorization: Bearer`.

`/Customer/V1/Login`  body `{eml, password, cnncScn:"1"}`
  -> `{userId, token, expireAt, refreshToken, refreshExpireAt, nickNm, lckYn, pwdChangeRequired}`

`/Customer/V1/Vehicles`  body `{}`  -> `{vehicles:[{vehlId, vin, isEv, saleMdlNm, xrclNm, ownerId, ...}]}`

`/Customer/V1/VehiclesFixDetail`  body `{vehlId}`  -> static detail (model, engine, seats; no SoC)

`/Customer/V1/VehiclesChangeDetail`  body `{vehlId}`  — **CACHED status, NO PIN, NO wake**
  (this is what the app shows on open; poll this for the regular update)
  -> `{btrSoc(%), trvgPsblDist(range), acumTrvgDist(odometer), btrChargingStat, btcgType,
       btcgCmplTimTim/Minu, btr80BtcgTimTim/Minu, btrRsqt, pcktUpdtDtm(last-updated),
       carStatIqDtm, avgTrvgDist, grssTrvgDist, grssAvgSpd, evYn, ...}`

EV status = **two-step** (needs remote PIN; wakes the car):
  `/Customer/V1/VehicleStatusCheckCmdEv`  body `{vehlId, pin}`
     -> `{rctlMnId, isPinLocked, failCount, maxRetryCount, errorCode, errorMessage}`
  `/Customer/V1/VehicleStatusCheckResultEv`  body `{rctlMnId, vehlId}`  (poll every ~4s; `retryFlag`)
     -> `{btrSoc(%), evTrvgDist(range), btrChargingStat, btcgType, btcgCmplTimTim/Minu,
          btr80BtcgTimTim/Minu, totalDrivingDistance, keyStat, drvtDoorStat, srfStat,
          hdeLampStat, *OpndStat (doors/hood/tailgate), isEv, retryFlag}`

Location = same two-step shape:
  `/Customer/V1/LocationFinderCmd`  body `{vehlId, pin, userLatitude, userLongitude}` -> `{rctlMnId, ...}`
  `/Customer/V1/LocationFinderResult`  body `{rctlMnId, vehlId}`
     -> `{pcktGpsLae(lat), pcktGpsLoe(lon), locExYn, carDist, rctlStatCode, retryFlag}`

Notes: only ONE remote command runs at a time ("previous command has not ended yet"); space
Cmd calls out. The PIN is the remote-control PIN with a lockout (`failCount`/`maxRetryCount`).
