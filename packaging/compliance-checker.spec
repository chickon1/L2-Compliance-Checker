# PyInstaller spec for the standalone desktop/server build — shared between
# Windows and Linux. PyInstaller doesn't cross-compile, so this must be run
# ON the OS you want an executable for (see packaging/README.md); it produces
# a Windows compliance-checker.exe when run on Windows, or a Linux
# compliance-checker binary when run on Linux, since sys.platform below
# reflects whichever OS PyInstaller itself is running on at build time.
#
#   pyinstaller packaging/compliance-checker.spec

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
project_root = Path(SPECPATH).parent

# netmiko dynamically imports a driver module per device_type (cisco_ios,
# juniper_junos, etc.) — static analysis alone misses most of these, so
# pull in everything netmiko ships rather than hand-listing hidden imports.
netmiko_datas, netmiko_binaries, netmiko_hidden = collect_all("netmiko")

hiddenimports = [
    "cryptography.hazmat.backends.openssl",
    *netmiko_hidden,
]
if sys.platform == "win32":
    hiddenimports += [
        "win32crypt",  # used for DPAPI-protecting the credential key at rest
        "win32ctypes.pywin32.win32crypt",
    ]

a = Analysis(
    [str(project_root / "src" / "compliance_checker" / "desktop.py")],
    pathex=[str(project_root / "src")],
    binaries=netmiko_binaries,
    datas=[
        (str(project_root / "src" / "compliance_checker" / "rules"), "rules_data"),
        (str(project_root / "frontend" / "dist"), "frontend_dist"),
        *netmiko_datas,
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="compliance-checker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
