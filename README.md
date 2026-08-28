# KGM Link for Home Assistant

> ## 🧪 Beta — EV status works
> Login and **EV status (battery %, range, charging state, time-to-charge, odometer)** are
> working against the live API. Uses a plaintext-body path that bypasses the app's message
> cipher (see [`research/PROTOCOL.md`](research/PROTOCOL.md)). Not yet published to HACS /
> hassfest-validated; vehicle **location** (device_tracker) is the next endpoint to wire.
> Reading live status **wakes the car** and needs your **remote-control PIN**.

Unofficial Home Assistant integration for **KGM Link** (KG Mobility / SsangYong
connected-car service), reverse-engineered from the iOS app's `tr-open-api.kgm-link.com`
API. Aimed first at the EV models exposed through the app (charge state, SoC, range,
climate, lock). Multi-vehicle accounts are supported (one HA device per car).

> Status: **early / pre-alpha.** The API works, but every request is wrapped in an
> AES + RSA + HMAC envelope that must be reimplemented before the client can talk to
> the server. See [`research/PROTOCOL.md`](research/PROTOCOL.md) for what is known and
> what is still blocked.

## Why this exists

KG Mobility ships no public API and no official HA integration. Owners who want their
car's charge/SoC in Home Assistant have no supported path. This project documents the
app's private API and provides a pure-Python client so HA can read status and (later)
send remote commands.

This is interoperability research against an API for a vehicle the author owns. No
credentials, tokens, VINs, or vendor secrets are committed to this repository.

## Install (HACS, once functional)

1. HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/arasuludag/kgm-link-ha` as an *Integration*.
2. Install **KGM Link**, restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **KGM Link** → log in.

## Architecture

```
custom_components/kgm_link/
  crypto.py        # request/response envelope (AES-CBC + RSA-2048 + HMAC-SHA256)  [BLOCKED]
  api.py           # endpoint client, session/JWT handling, status poll loop
  coordinator.py   # DataUpdateCoordinator — wake vs. cached-read strategy
  config_flow.py   # login UI
  sensor.py        # SoC, range, charging state, ...  (field map TBD post-decrypt)
```

## The one hard blocker

The envelope's HMAC signing recipe (`X-Signature`) and the server RSA public key must
be recovered from the app binary. The crypto module (`KMS_IOS_FRAMEWORK`) ships
**unencrypted**; the orchestration lives in the main binary, which is FairPlay-encrypted
but dumpable because the app runs natively on Apple Silicon. See `research/PROTOCOL.md`.

## Contributing / captures

Drop Proxyman HAR exports in `captures/` (gitignored). One flow per file. Never paste
raw captures into issues — they contain live bearer tokens and your VIN.

## License

MIT. Not affiliated with, endorsed by, or supported by KG Mobility / SsangYong.
