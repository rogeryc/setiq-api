"""Symmetric encryption for secrets we have to store (Meta page tokens
mostly). Uses Fernet (AES-128-CBC + HMAC-SHA256) from `cryptography`.

We never want raw page tokens sitting in the database — a DB read is
enough to act as the customer otherwise. Tokens get encrypted on the
way in, decrypted on the way out, and the symmetric key lives only in
the runtime environment (`META_TOKEN_ENCRYPTION_KEY`).

Rotation: changing the key invalidates ALL existing ciphertexts. We
don't support multi-key decryption today — when we rotate, every tenant
re-OAuths. Acceptable for MVP; revisit if the user base grows past a
handful of pilots.
"""
from __future__ import annotations

import logging
from functools import cache

from cryptography.fernet import Fernet, InvalidToken

from setiq.config import settings

logger = logging.getLogger(__name__)

# Sentinel applied to ciphertexts so we can tell encrypted blobs apart
# from any legacy plaintext tokens that might still be in the DB during
# the transition window. Pre-existing plaintext tokens decrypt as-is
# (no key prefix) — they'll get re-encrypted on next OAuth.
_CIPHERTEXT_PREFIX = "enc:v1:"


@cache
def _fernet() -> Fernet:
    if not settings.meta_token_encryption_key:
        raise RuntimeError(
            "META_TOKEN_ENCRYPTION_KEY is not set — generate one with "
            "`Fernet.generate_key()` and add it to .env."
        )
    return Fernet(settings.meta_token_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    """Encrypt a string and return a versioned ciphertext that round-trips
    safely through JSONB storage."""
    token = _fernet().encrypt(plaintext.encode()).decode()
    return f"{_CIPHERTEXT_PREFIX}{token}"


def decrypt_token(stored: str) -> str:
    """Inverse of encrypt_token. Strings without the version prefix are
    returned unchanged (legacy plaintext during transition)."""
    if not stored:
        return stored
    if not stored.startswith(_CIPHERTEXT_PREFIX):
        # Pre-existing plaintext token from before encryption was wired —
        # log once and return it so the caller can still use it. Will get
        # re-encrypted on the next OAuth round-trip for that tenant.
        logger.warning("decrypt_token: encountered legacy plaintext token; will re-encrypt on next OAuth")
        return stored
    ciphertext = stored[len(_CIPHERTEXT_PREFIX):]
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        # Either the key changed (no rotation support today) or the
        # ciphertext got truncated. Either way, the token is unusable.
        raise RuntimeError("page token decryption failed — was META_TOKEN_ENCRYPTION_KEY rotated?") from e
