"""Linux-only pre-flight dependency check for the packaged binary.

Before `desktop.py` reads/writes the credential-encryption key via the OS
keyring, confirm a Secret Service provider is actually reachable. Without
this, the failure a user sees on first launch (on a machine with no keyring
daemon running — e.g. a minimal desktop install, or a fresh account that's
never had one configured) is a raw `keyring.errors.NoKeyringError`
traceback. This instead names the problem and offers to install
gnome-keyring (a Secret Service provider that works even outside a full
GNOME desktop) via whichever package manager the machine actually has —
only running anything with `sudo` after an explicit y/N confirmation typed
into that same terminal.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

_PACKAGE_MANAGERS: list[tuple[str, list[str]]] = [
    ("apt-get", ["sudo", "apt-get", "install", "-y", "gnome-keyring"]),
    ("dnf", ["sudo", "dnf", "install", "-y", "gnome-keyring"]),
    ("yum", ["sudo", "yum", "install", "-y", "gnome-keyring"]),
    ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "gnome-keyring"]),
    ("zypper", ["sudo", "zypper", "install", "-y", "gnome-keyring"]),
]


def _secret_service_reachable() -> bool:
    import keyring
    from keyring.errors import KeyringError, NoKeyringError

    try:
        keyring.get_password("compliance-checker", "__preflight_probe__")
        return True
    except NoKeyringError:
        return False
    except KeyringError:
        # Some other backend-specific error (e.g. locked, permission denied)
        # -- a backend does exist, it's just not cooperating right now,
        # which is a different problem than "nothing is installed". Don't
        # offer to install anything on top of that.
        return True


def _find_installer() -> list[str] | None:
    for binary, command in _PACKAGE_MANAGERS:
        if shutil.which(binary):
            return command
    return None


def ensure_secret_service() -> None:
    """Best-effort only — never raises. If this doesn't resolve things,
    desktop.py's own keyring call surfaces the real error afterwards, so a
    declined/failed/impossible install here just falls through to that."""
    if _secret_service_reachable():
        return

    # flush=True on every print here: this runs right before code that may
    # raise (the real keyring error surfacing afterwards if this doesn't
    # resolve things), so these status lines must land in the terminal in
    # order rather than sitting in a stdout buffer behind that traceback.
    print(
        "No keyring/Secret Service backend detected -- this app stores the "
        "saved device-credential encryption key in your OS keyring rather "
        "than a plaintext file, and needs one running (GNOME Keyring or "
        "KWallet).",
        flush=True,
    )

    command = _find_installer()
    if command is None:
        print(
            "Couldn't detect a supported package manager (apt/dnf/yum/pacman/"
            "zypper) to install one automatically -- install gnome-keyring "
            "(or your desktop's own keyring service) yourself, then relaunch.",
            flush=True,
        )
        return

    if not sys.stdin.isatty():
        print(f"Run this yourself, then relaunch: {' '.join(command)}", flush=True)
        return

    answer = input(f"Install it now with '{' '.join(command)}'? [y/N] ").strip().lower()
    if answer != "y":
        print("Skipping install -- relaunch after installing it yourself if you change your mind.", flush=True)
        return

    result = subprocess.run(command)
    if result.returncode != 0:
        print("Install command failed -- see the output above.", flush=True)
        return

    print(
        "Installed. Note a keyring daemon usually needs an active login "
        "session to unlock -- if it's still not detected after this, try "
        "logging out and back in, then relaunch.",
        flush=True,
    )
