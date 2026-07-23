"""Password hashing and session tokens.

Pure functions only, no repository/DB access here — mirrors credentials.py's
scope (which does Fernet encryption the same way). Kept dependency-free so
repository.py can import from here without any risk of a circular import.
"""

from __future__ import annotations

import secrets

import bcrypt

SESSION_COOKIE_NAME = "cc_session"
SESSION_TTL_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)
