"""Standalone entry point, bundled by PyInstaller into a single executable
(see packaging/compliance-checker.spec) — `main()` is the entry point on
both platforms it's shipped for:

- Windows: runs the backend in a background thread and opens it in a
  native window via pywebview, so the whole app is one process with no
  browser tab and no manual server startup.
- Linux: pywebview would need GTK/WebKit or Qt bundled, which PyInstaller
  can't self-contain as reliably as it does on Windows, so this just runs
  the server in the foreground and opens it in the user's normal browser
  instead — same experience as the dev/server setup, just as one binary.

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


def _protect_key(raw_key: bytes) -> bytes:
    """Encrypt the Fernet key itself using Windows DPAPI, tied to the
    current Windows user account (CryptProtectData with no
    CRYPTPROTECT_LOCAL_MACHINE flag scopes it to the user, matching
    %APPDATA%'s own per-user scoping). Without this, the key file sits in
    plaintext right next to the database it protects — anyone who copies
    the whole data folder gets both the encrypted passwords and the key to
    decrypt them. With DPAPI, that same copy is useless without also being
    logged in as this exact Windows user on this exact machine."""
    import win32crypt

    return win32crypt.CryptProtectData(raw_key, "compliance-checker credential key", None, None, None, 0)


def _unprotect_key(blob: bytes) -> bytes:
    import win32crypt

    return win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1]


def _load_or_create_key_linux() -> bytes:
    """Store the raw Fernet key straight in the OS keyring (Secret Service —
    GNOME Keyring/KWallet) instead of a file on disk, so there's nothing
    for someone to copy off the filesystem the way there would be with a
    plaintext key file. Requires a real desktop session with a keyring
    daemon running; on a headless box this raises rather than silently
    falling back to something weaker."""
    import keyring

    service, username = "compliance-checker", "credential-key"
    existing = keyring.get_password(service, username)
    if existing is not None:
        return existing.encode()

    key_bytes = Fernet.generate_key()
    keyring.set_password(service, username, key_bytes.decode())
    return key_bytes


def _load_or_create_key_file(data_dir: Path) -> bytes:
    """Dev-only fallback for platforms with no real key-protection path
    wired up here (e.g. running this launcher on macOS). Not used by the
    Windows or Linux shipped builds — see the win32 (DPAPI) and linux
    (OS keyring) paths above."""
    key_path = data_dir / "credential.key"
    if key_path.exists():
        return key_path.read_bytes()

    key_bytes = Fernet.generate_key()
    key_path.write_bytes(key_bytes)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key_bytes


def _ensure_environment() -> None:
    data_dir = _app_data_dir()

    if sys.platform == "win32":
        key_path = data_dir / "credential.key"
        if key_path.exists():
            key_bytes = _unprotect_key(key_path.read_bytes())
        else:
            key_bytes = Fernet.generate_key()
            key_path.write_bytes(_protect_key(key_bytes))
    elif sys.platform.startswith("linux"):
        # Absolute import, not relative: PyInstaller runs this file as
        # __main__ rather than as compliance_checker.desktop, so a relative
        # import (`from .linux_preflight import ...`) fails at runtime in
        # the frozen build even though it'd work fine under a normal
        # `python -m compliance_checker.desktop` or the pip console-script
        # entry point.
        from compliance_checker.linux_preflight import ensure_secret_service

        ensure_secret_service()
        key_bytes = _load_or_create_key_linux()
    else:
        key_bytes = _load_or_create_key_file(data_dir)

    os.environ["CC_CREDENTIAL_KEY"] = key_bytes.decode()

    os.environ.setdefault("CC_DB_PATH", str(data_dir / "compliance_checker.db"))
    os.environ.setdefault("CC_RULES_DIR", str(_base_dir() / "rules_data"))


def main() -> None:
    _ensure_environment()

    # Imported after env vars are set, and only here, so a plain `uvicorn
    # compliance_checker.bootstrap:create_application` (dev/server use)
    # never needs pywebview installed at all.
    import uvicorn

    # Absolute import for the same reason as the linux_preflight import
    # above — this file runs as __main__ under PyInstaller.
    from compliance_checker.bootstrap import create_application

    app = create_application()
    url = "http://127.0.0.1:8444"

    if sys.platform == "win32":
        import webview

        server_thread = threading.Thread(
            target=lambda: uvicorn.run(app, host="127.0.0.1", port=8444, log_level="warning"),
            daemon=True,
        )
        server_thread.start()
        time.sleep(1.5)  # give uvicorn a moment to bind before pointing the window at it

        webview.create_window("Compliance Checker", url, width=1440, height=900)
        webview.start()
    else:
        # Linux build: no native window (pywebview needs GTK/WebKit or Qt,
        # which PyInstaller can't reliably self-contain the way it can on
        # Windows) — run the server in the foreground and use it through a
        # normal browser tab, same as the dev/server setup already works.
        import webbrowser

        def _open_browser_soon() -> None:
            time.sleep(1.5)
            try:
                webbrowser.open(url)
            except Exception:
                pass  # e.g. no DISPLAY on a headless box — the printed URL below still works

        threading.Thread(target=_open_browser_soon, daemon=True).start()
        print(f"Compliance Checker running at {url} (Ctrl+C to stop)")
        uvicorn.run(app, host="127.0.0.1", port=8444, log_level="warning")


if __name__ == "__main__":
    main()
