"""KGM Link request envelope (plaintext-body path).

The message body cipher (`TwoWayCryptoManager.makeKeyAndIV`) is deliberately obfuscated
and was never cracked — but it turns out we don't need it. The server honours
`X-Encrypted: False` with a **plaintext JSON body**, and the signature only covers
`timestamp + nonce + S` (not the body), so the signed envelope still validates.

Confirmed live: with the envelope below + `X-Encrypted: False` + a plaintext body, the
server parses the body and replies in plaintext.

Envelope (per request):
  S           = uppercase_hex(SecRandom(32))                 # ephemeral session key
  X-Timestamp = ISO8601 UTC
  X-Nonce     = base64( RSA-2048 PKCS#1 v1.5 ( S.utf8 ) )    # server key from /Common/V1/PublicKey
  X-Signature = base64( HMAC-SHA256( key=S.utf8, msg=(ts + nonce + S).utf8 ) )
  X-Encrypted = False
  Authorization: Bearer <JWT>   (after Login)
  body        = plaintext JSON
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone
from secrets import token_bytes


def load_public_key(spki_b64: str):
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    return load_der_public_key(base64.b64decode(spki_b64))


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope_headers(public_key, *, tz_offset: str = "+03:00", token: str | None = None) -> dict[str, str]:
    """Signed (but unencrypted) envelope headers for one request."""
    from cryptography.hazmat.primitives.asymmetric import padding

    s = token_bytes(32).hex().upper()
    nonce = base64.b64encode(public_key.encrypt(s.encode(), padding.PKCS1v15())).decode("ascii")
    ts = _now_ts()
    sig = base64.b64encode(
        hmac.new(s.encode(), (ts + nonce + s).encode(), hashlib.sha256).digest()
    ).decode("ascii")
    headers = {
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": sig,
        "X-Encrypted": "False",
        "IsMobile": "True",
        "LangCode": "en",
        "Offset": tz_offset,
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "Ccs/1.0.7.4 CFNetwork/3860.700.1 Darwin/25.6.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
