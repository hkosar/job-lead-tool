"""Symmetric encryption for API keys stored at rest (spec section 9).

Uses Fernet (AES-128-CBC + HMAC) keyed from the FERNET_KEY environment variable.
FERNET_KEY may be a proper Fernet key OR any random secret string (hosting
platforms can auto-generate one); non-Fernet values are hashed into a valid key.
If no key is set at all we fall back to a no-op so the app still runs in
development.
"""
from __future__ import annotations
import os, json, base64


def _fernet():
    key = os.getenv("FERNET_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        try:
            return Fernet(key.encode())   # value is already a valid Fernet key
        except Exception:
            # Any other secret string (e.g. a random value the hosting platform
            # generated) is hashed into a valid 32-byte key, so encryption works
            # without the operator ever hand-crafting a Fernet key.
            import hashlib
            derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
            return Fernet(derived)
    except Exception as e:
        print("Fernet init failed (storing creds unencrypted):", e)
        return None


def encrypt_creds(creds: dict) -> str:
    """dict -> encrypted token string (or plain base64 if no key set)."""
    raw = json.dumps(creds or {}).encode("utf-8")
    f = _fernet()
    if f is None:
        return "plain:" + base64.b64encode(raw).decode("ascii")
    return "enc:" + f.encrypt(raw).decode("ascii")


def decrypt_creds(token: str | None) -> dict:
    """encrypted token string -> dict. Tolerates plain/legacy/empty values."""
    if not token:
        return {}
    try:
        if token.startswith("enc:"):
            f = _fernet()
            if f is None:
                return {}
            return json.loads(f.decrypt(token[4:].encode("ascii")).decode("utf-8"))
        if token.startswith("plain:"):
            return json.loads(base64.b64decode(token[6:]).decode("utf-8"))
        # legacy: a raw dict was stored as JSON
        return json.loads(token)
    except Exception as e:
        print("decrypt_creds failed:", e)
        return {}
