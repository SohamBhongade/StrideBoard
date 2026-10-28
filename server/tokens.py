"""Phone tokens (the code a phone uses to send steps) are never stored readable.

The database keeps two things per person:
  api_token       the token, sealed with AES-256-GCM (the app still needs to show it to its
                  owner, for the iPhone Shortcut and the Android app, so it can't be one-way);
  api_token_hash  a keyed fingerprint of it, so /api/steps can find the owner without unsealing
                  every row.
Both keys come from STRIDEBOARD_SECRET_KEY, which lives in the WSGI file and not in the
database: a stolen copy of the database alone can't send steps as anyone.
If the secret key ever changes, old tokens stop working and everyone gets a new one
automatically the next time they open the app.
"""
import base64
import hashlib
import hmac
import os
import secrets

import config

PREFIX = "enc1:"


def _secret():
    return os.environ.get("STRIDEBOARD_SECRET_KEY", config.SECRET_KEY).encode()


def _key(purpose):
    return hashlib.sha256(b"strideboard-token|" + purpose + b"|" + _secret()).digest()


def new_token():
    return secrets.token_urlsafe(24)


def fingerprint(token):
    """The lookup value for a token (same token, same fingerprint)."""
    return hmac.new(_key(b"lookup"), str(token).encode(), hashlib.sha256).hexdigest()


def seal(token):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    box = AESGCM(_key(b"seal")).encrypt(nonce, str(token).encode(), b"api_token")
    return PREFIX + base64.urlsafe_b64encode(nonce + box).decode()


def unseal(value):
    """The readable token, or None if it was sealed with a different secret key."""
    if not value:
        return None
    if not value.startswith(PREFIX):
        return value                      # from before tokens were sealed (create_tables seals these)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        raw = base64.urlsafe_b64decode(value[len(PREFIX):])
        return AESGCM(_key(b"seal")).decrypt(raw[:12], raw[12:], b"api_token").decode()
    except Exception:
        return None


def is_sealed(value):
    return bool(value) and value.startswith(PREFIX)
