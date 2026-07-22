# PyInstaller spec for the standalone Windows desktop build.
#
# Must be built ON Windows (PyInstaller doesn't cross-compile) — see
# packaging/README.md for the full build steps. Run from the project root:
#
#   pyinstaller packaging/compliance-checker.spec
#
# Produces a single dist/compliance-checker.exe.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
project_root = Path(SPECPATH).parent

# netmiko dynamically imports a driver module per device_type (cisco_ios,
# juniper_junos, etc.) — static analysis alone misses most of these, so
# pull in everything netmiko ships rather than hand-listing hidden imports.
netmiko_datas, netmiko_binaries, netmiko_hidden = collect_all("netmiko")

a = Analysis(
    [str(project_root / "src" / "compliance_checker" / "desktop.py")],
    pathex=[str(project_root / "src")],
    binaries=netmiko_binaries,
    datas=[
        (str(project_root / "src" / "compliance_checker" / "rules"), "rules_data"),
        (str(project_root / "frontend" / "dist"), "frontend_dist"),
        *netmiko_datas,
    ],
    hiddenimports=[
        "cryptography.hazmat.backends.openssl",
        "win32crypt",  # used for DPAPI-protecting the credential key at rest
        "win32ctypes.pywin32.win32crypt",
        *netmiko_hidden,
    ],
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
