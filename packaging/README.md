# Building the standalone Windows app

This turns the compliance-checker web app into a single `compliance-checker.exe`
that runs entirely on your own machine — no browser tab, no separate server
process to remember to start.

This has to be built **on Windows itself** — PyInstaller bundles the actual
Python interpreter and native extensions for whatever OS you run it on, so a
Linux-built exe won't work on Windows and vice versa. These steps assume a
Windows machine with Python 3.12 and Node.js already installed.

## 1. Get the code onto the Windows machine

Copy (or `git clone`) the whole `compliance-checker` folder over from this
VM — the easiest path is probably the same VS Code file-download trick we
used for the GNS3 appliance file earlier, just for the whole folder (zip it
first, e.g. `zip -r compliance-checker.zip compliance-checker/` on this VM,
then download and unzip the archive on Windows).

## 2. Build the frontend

```
cd compliance-checker\frontend
npm install
npm run build
```

This produces `frontend\dist\` — the packaged app serves this directly, no
Vite dev server involved.

## 3. Set up the Python environment and install desktop dependencies

```
cd compliance-checker
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[desktop]"
```

That installs the app itself plus `pywebview` and `pyinstaller`.

## 4. Build the .exe

```
pyinstaller packaging\compliance-checker.spec
```

The finished executable lands at `dist\compliance-checker.exe`. You *can*
stop here and just run that file directly — but it won't show up in
Settings > Apps, won't have Start Menu shortcuts, and won't have a proper
uninstaller. For that, do step 5.

## 5. Build the installer (adds Start Menu shortcuts + uninstall support)

Install [Inno Setup](https://jrsoftware.org/isinfo.php) (free), then either:

- Open `packaging\compliance-checker.iss` in the Inno Setup Compiler GUI and
  click **Compile**, or
- From the command line: `iscc packaging\compliance-checker.iss`

This produces `packaging\installer_output\ComplianceChecker-Setup.exe`. That
installer:

- Installs to `%LOCALAPPDATA%\Programs\ComplianceChecker` — no admin rights
  or UAC prompt needed
- Adds Start Menu shortcuts (launch + uninstall) and an optional desktop icon
- Registers a normal uninstall entry under **Settings > Apps** (or Control
  Panel > Programs and Features) — no manual file cleanup needed later
- Leaves `%APPDATA%\ComplianceChecker\` (the database + credential
  encryption key) in place on uninstall, matching how most Windows apps
  handle user data — delete that folder by hand if you ever want a
  completely clean wipe

## What happens on first run

- A per-user data folder is created automatically at
  `%APPDATA%\ComplianceChecker\` — this holds the SQLite database and an
  auto-generated encryption key for stored credential-profile passwords.
  Nothing needs to be configured by hand.
- That encryption key is itself protected with Windows DPAPI
  (`CryptProtectData`), tied to your specific Windows user account and
  machine — so even if someone copies the whole `ComplianceChecker` data
  folder elsewhere, the key file inside it is useless without also being
  logged in as you on this machine. Device credential *passwords* are
  encrypted with that key using Fernet (AES128-CBC + HMAC) before ever
  touching the database.
- The app starts with an empty device inventory, same as the dev version —
  use the Import page to discover/add your lab devices.

## If something goes wrong

- **Missing module errors on launch**: netmiko has a lot of per-platform
  driver files that PyInstaller's static analysis can miss. The spec already
  pulls in `collect_all("netmiko")` to cover this, but if a new netmiko
  version adds something outside that net, the error message will name the
  missing module — add it to `hiddenimports` in the `.spec` file and rebuild.
  The same applies if `win32crypt` (used for DPAPI) fails to import — it's
  already listed in `hiddenimports`, but pywin32 occasionally needs its
  post-install script re-run: `python .venv\Scripts\pywin32_postinstall.py -install`.
- **Blank window on launch**: usually means the backend thread hasn't
  finished binding to port 8444 before the window tries to load it. The
  launcher already waits 1.5s before opening the window
  (`src/compliance_checker/desktop.py`); if it's still blank, try increasing
  that delay slightly and rebuilding.
- **Antivirus/SmartScreen flags the .exe**: expected for an unsigned,
  freshly-built executable — PyInstaller binaries often get flagged since
  they're unfamiliar to reputation-based scanners, not because of anything
  in this codebase. Code-signing would fix this longer-term but requires a
  certificate; not set up here.

This whole build/test cycle hasn't been run against a real Windows machine
yet — treat the first attempt as a shakeout run, and paste back whatever
error comes up if it doesn't launch cleanly on the first try. Same goes for
the Inno Setup installer in step 5 — it's untested for the same reason
(no Windows machine to run it on from here).

## Hardening notes

What's already in place for the packaged build, and what's a deliberate
non-goal:

- **Loopback-only**: the backend binds to `127.0.0.1`, never a real network
  interface — nothing outside the machine can reach it, regardless of
  firewall state.
- **No interactive API docs in production**: `create_application()` (what
  the desktop build uses) disables `/docs`, `/redoc`, and `/openapi.json`,
  so the full API schema isn't browsable even locally. `create_mock_application()`
  (used only for local dev/demo) still has them.
- **Credential encryption key**: auto-generated on first run, stored at
  `%APPDATA%\ComplianceChecker\credential.key`. This protects stored
  device-credential passwords if the database file is copied elsewhere
  (e.g. into a synced cloud folder) — it does **not** protect against
  another process/user with access to the same Windows account, since
  that's already inside the same trust boundary Windows itself defines via
  `%APPDATA%`.
- **No login screen on the app itself**: anyone who can launch the exe on
  your machine can use it — there's no separate password gate in front of
  the UI. Given this is a single-user desktop tool rather than a shared
  service, that's treated as acceptable for now; say the word if you want
  a PIN/password gate added, it'd be a real (if fairly small) feature
  addition, not a config flip.
- **Unsigned executable**: no code-signing certificate is set up, so
  Windows SmartScreen/antivirus will likely flag a fresh build the first
  time it runs (see the SmartScreen note above). This is normal for
  unsigned binaries and isn't indicative of anything wrong with the build.
