"""Single-passcode gate, enforced SERVER-SIDE (see spec section 9).

- The passcode is stored as a bcrypt hash (never in plain text).
- On a correct passcode we issue a signed, expiring session token (HMAC over an
  expiry timestamp using SESSION_SECRET). The token is stateless: it survives a
  server restart and needs no session table.
- Login attempts are rate-limited in memory to slow brute-force guessing.

This replaces the prototype's client-side gate, which was illustrative only.
"""
from __future__ import annotations
import os, hmac, hashlib, base64, time, threading

import bcrypt

SESSION_TTL = 60 * 60 * 12          # 12 hours
_MAX_ATTEMPTS = 8                   # per window, per client
_WINDOW = 300                       # 5 minutes
_attempts: dict[str, list[float]] = {}
_lock = threading.Lock()


# ---------- passcode hashing ----------
def set_passcode(plain: str) -> str:
    # bcrypt has a 72-byte limit; passcodes are short, but guard anyway.
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("ascii")


def check_passcode(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("ascii"))
    except Exception:
        return False


# ---------- signed session tokens ----------
def _secret() -> bytes:
    return os.getenv("SESSION_SECRET", "dev-insecure-secret").encode("utf-8")


def create_session_token(ttl: int = SESSION_TTL) -> str:
    expiry = str(int(time.time()) + ttl)
    sig = hmac.new(_secret(), expiry.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{expiry}.{sig}".encode()).decode("ascii")


def verify_session_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        expiry, sig = raw.split(".", 1)
        expected = hmac.new(_secret(), expiry.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        return int(expiry) > int(time.time())
    except Exception:
        return False


# ---------- rate limiting ----------
def too_many_attempts(client_id: str) -> bool:
    now = time.time()
    with _lock:
        hits = [t for t in _attempts.get(client_id, []) if now - t < _WINDOW]
        _attempts[client_id] = hits
        return len(hits) >= _MAX_ATTEMPTS


def record_attempt(client_id: str) -> None:
    with _lock:
        _attempts.setdefault(client_id, []).append(time.time())


def clear_attempts(client_id: str) -> None:
    with _lock:
        _attempts.pop(client_id, None)
