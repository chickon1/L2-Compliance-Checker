"""Environment-driven settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    port: int
    credential_key: str | None
    rules_dir: str
    db_path: str


def load_settings() -> Settings:
    return Settings(
        port=int(os.environ.get("CC_PORT", "8444")),
        credential_key=os.environ.get("CC_CREDENTIAL_KEY"),
        rules_dir=os.environ.get("CC_RULES_DIR", "src/compliance_checker/rules"),
        db_path=os.environ.get("CC_DB_PATH", "data/compliance_checker.db"),
    )
