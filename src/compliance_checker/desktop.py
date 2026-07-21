"""Standalone desktop entry point.

Runs the FastAPI backend in a background thread and opens it in a native
window via pywebview, so the whole app is one process with no browser tab
and no manual server startup. This is what gets bundled into a single
Windows .exe by PyInstaller (see packaging/compliance-checker.spec) —
`main()` is the executable's entry point.

Unlike the dev setup (this file isn't used there at all — `bootstrap.py`'s
factories are run directly under `uvicorn`, with Vite serving the frontend
separately on :5173), a packaged desktop build has no shell to set
environment variables in, so this module generates and persists a
credential key and a per-user database path on first run instead of
requiring `CC_CREDENTIAL_KEY` to already be set.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from cryptography.fernet import Fernet


def _base_dir() -> Path:
    """Where bundled resources (rules/, the built frontend) live."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent.parent


def _app_data_dir() -> Path:
    """Where the database and generated credential key persist across runs,
    per-user. %APPDATA%\\ComplianceChecker on Windows; a dotfolder in the
    home directory anywhere else (e.g. for testing this launcher on Linux/
    Mac before building the actual Windows .exe)."""
    appdata = os.environ.get("APPDATA")
    data_dir = Path(appdata) / "ComplianceChecker" if appdata else Path.home() / ".compliance-checker"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _ensure_environment() -> None:
    data_dir = _app_data_dir()

    key_path = data_dir / "credential.key"
    if key_path.exists():
        key = key_path.read_text().strip()
    else:
        key = Fernet.generate_key().decode()
        key_path.write_text(key)
        try:
            # Meaningful on Linux/Mac (e.g. testing this launcher before
            # building the actual Windows exe); on Windows this just flips
            # the read-only attribute — the real access boundary there is
            # %APPDATA% already being scoped to the owning user by NTFS.
            os.chmod(key_path, 0o600)
        except OSError:
            pass
    os.environ["CC_CREDENTIAL_KEY"] = key

    os.environ.setdefault("CC_DB_PATH", str(data_dir / "compliance_checker.db"))
    os.environ.setdefault("CC_RULES_DIR", str(_base_dir() / "rules_data"))


def main() -> None:
    _ensure_environment()

    # Imported after env vars are set, and only here, so a plain `uvicorn
    # compliance_checker.bootstrap:create_application` (dev/server use)
    # never needs pywebview installed at all.
    import uvicorn
    import webview

    from .bootstrap import create_application

    app = create_application()

    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=8444, log_level="warning"),
        daemon=True,
    )
    server_thread.start()
    time.sleep(1.5)  # give uvicorn a moment to bind before pointing the window at it

    webview.create_window("Compliance Checker", "http://127.0.0.1:8444", width=1440, height=900)
    webview.start()


if __name__ == "__main__":
    main()
