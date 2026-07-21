"""Encryption helpers for credential secrets stored in the database.

The encryption key comes from CC_CREDENTIAL_KEY and is never stored
alongside the encrypted values (they live in the SQLite DB; the key stays
in the environment).
"""

from __future__ import annotations

from typing import NamedTuple

from cryptography.fernet import Fernet


class Credentials(NamedTuple):
    username: str
    password: str


def encrypt_secret(key: str, plaintext: str) -> bytes:
    return Fernet(key.encode()).encrypt(plaintext.encode())


def decrypt_secret(key: str, ciphertext: bytes) -> str:
    return Fernet(key.encode()).decrypt(ciphertext).decode()
