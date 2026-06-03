"""Symmetric encryption for API keys stored at rest (spec section 9).

Uses Fernet (AES-128-CBC + HMAC) with a key from FERNET_KEY in .env. If no key
is set we fall back to a no-op so the app still runs in development — but a real
key is generated into .env by setup, so encryption is on by default.
"""
from __future__ import annotations
import os, json, base64


def _fernet():
    key = os.getenv("FERNET_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
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
