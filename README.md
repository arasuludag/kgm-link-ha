# KGM Link for Home Assistant

Unofficial Home Assistant integration for **KGM Link** (KG Mobility / SsangYong
connected-car service), reverse-engineered from the iOS app's `tr-open-api.kgm-link.com`
API. Multi-vehicle accounts are supported — one HA device per car.

> ## 🧪 Beta
> Status, location and the full remote-command set are implemented and the protocol is
> documented in [`research/PROTOCOL.md`](research/PROTOCOL.md). Developed against a
> **Torres EVX** on the Turkish region (`tr`); other models and regions are untested.
> Not yet published to HACS.

## What you get

### Reads

| Entity | Source | Cost |
|---|---|---|
| Battery %, range, odometer, charging status, time-to-full, time-to-80%, last updated | cached poll | free |
| Charging (binary sensor) | cached poll | free |
| Doors, tailgate, hood, sunroof, headlamps (binary sensors) | wake only | wakes the car |
| Location (device tracker) | on demand | wakes the car |

The regular 15-minute poll uses the same cached endpoint the app reads when you open it:
no PIN, no wake, no drain on the 12 V battery. Door and lamp states are not in that
payload, so they stay *unknown* until you press **Refresh (wake car)** and then hold
that value until the next wake. They are not live.

### Controls

| Entity | What it does |
|---|---|
| `lock` **Doors** | Lock / unlock |
| `switch` **Charge** | Start or stop charging immediately, independent of the EVSE |
| `climate` **Climate** | Remote preconditioning — target temperature and on/off |
| `number` **Climate run time** | 1–10 minutes (the app's own cap) |
| `switch` **Defrost**, **Rear window heat** | Staged for the next climate start |
| `select` **Seats** ×6 | Heat/vent level per seat, staged for the next climate start |
| `button` **Flash lights**, **Horn and lights**, **Lights off** | Find the car |
| `button` **Locate vehicle**, **Refresh (wake car)** | On-demand wake reads |

Rear-row seat selects and the horn button ship **disabled** — enable them in the entity
registry if your car has those seats or you actually want the horn.

#### Why climate looks the way it does

The API has no thermostat. `RemoteEngineStartEv` is a single one-shot call carrying the
temperature, the run time, defrost, rear-window heat and all six seat levels at once, and
the car shuts the session down by itself when the time is up. So the number/switch/select
entities *stage* the payload and the climate entity fires it. The climate entity is
`assumed_state`: it shows what was asked for and returns to off when the run time
elapses.

## Two things to know before you rely on this

**Command results are not confirmed.** The car reports the outcome of a remote command
by Firebase push, which Home Assistant cannot receive — the app itself falls back to
"check the vehicle status" when that push fails. So a command that returns successfully
means *the server accepted it*, not *the car did it*. The integration sets state
optimistically and re-reads the free cached endpoint afterwards, which catches charging
changes but cannot see door locks. **Do not treat the lock entity as proof the car is
locked.** Press Refresh for the truth.

**The remote PIN locks out.** A handful of wrong attempts and the PIN is locked until you
reset it in the app. The integration never retries a command after a PIN-related
rejection, and only ever sends one command at a time (the server allows no more).

## Install

1. HACS → Integrations → ⋮ → Custom repositories → add
   `https://github.com/arasuludag/kgm-link-ha` as an *Integration*.
2. Install **KGM Link**, restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **KGM Link**.
4. Enter your KGM Link email, password, remote-control PIN, and region (`tr`).

The PIN is required for anything that wakes or commands the car. It is stored in the
config entry like any other HA credential.

Sessions expire on the server side — both the access token and the refresh token. The
integration recovers on its own by logging back in with the stored credentials, so an
expired session is not something you have to act on. You are only prompted to sign in
again if the password itself stops working.

> **Security note:** installing this puts *unlock* and *climate start* behind your Home
> Assistant. Anyone with access to your HA — a shared dashboard, a guest account, a
> compromised token — can unlock the car. Scope your users accordingly.

## Architecture

```
custom_components/kgm_link/
  crypto.py        # signed request envelope (RSA-2048 + HMAC-SHA256)
  api.py           # endpoint client, JWT refresh, command bodies, wake/poll loop
  coordinator.py   # cached-poll vs. wake strategy; command dispatch
  entity.py        # shared device/entity base
  status.py        # reads the server's door/lock description strings
  config_flow.py   # login UI
  sensor.py binary_sensor.py device_tracker.py button.py
  lock.py switch.py climate.py number.py select.py
```

The app encrypts request bodies with an obfuscated AES key derivation. **That cipher is
not needed:** the signature covers only the timestamp, nonce and session key — not the
body — so sending `X-Encrypted: False` with a plaintext JSON body is accepted, and the
server replies in plaintext. See `research/PROTOCOL.md` §1.3b.

## Tests

```sh
pytest tests            # or: python3 tests/run.py
```

They run without Home Assistant installed — the request bodies and status parsing are
pure Python, and the suite checks them against the schemas in `research/PROTOCOL.md` §7.

## Contributing

`research/PROTOCOL.md` is the reference: endpoints, request schemas, enums, and how they
were recovered. Two sources, and it matters which you reach for:

- **The app binary** (`research/dump_swift_fields.py`) gives endpoint paths, response
  schemas, and the *shape* of a request body — field count, order and types.
- **The server** gives request *key names*. Request bodies declare a Swift `CodingKeys`
  enum whose raw values are the real JSON keys, and those are abbreviated beyond guessing
  (`acTemperature` → `aconTmpt`, `timeoutToTurnOffEngine` → `tot`). They are compiled to
  instruction immediates, so they are not in the binary as text. The server names the
  first missing required field on every rejection, which walks a body out one field per
  request — and a rejected body never reaches the car, so it costs nothing.

So you usually do **not** need a packet capture, but you do need the server. See §7.2 and
§7.5.

If you do capture traffic, keep HAR exports in `captures/` (gitignored) and never paste
raw captures into issues: they contain live bearer tokens and your VIN.

Adding a region means contributing that region's host; its server key is fetched at
runtime, not embedded.

This is interoperability research against an API for a vehicle the author owns. No
credentials, tokens, VINs, or vendor secrets are committed to this repository.

## License

MIT. Not affiliated with, endorsed by, or supported by KG Mobility / SsangYong.
