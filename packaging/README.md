# Building the standalone Windows app and Linux build

This turns the compliance-checker web app into a single executable that runs
entirely on your own machine.

- **Windows**: installs from a signed `ComplianceChecker.msi`; the app opens
  in its own native window (pywebview) — no browser tab, no separate server
  process to remember to start.
- **Linux**: `compliance-checker` runs the server and opens it in your normal
  browser (`http://127.0.0.1:8444`) — same experience as running the app
  in dev, just as one binary instead of a venv + `npm run build` + `uvicorn`.

## Recommended: let GitHub Actions build both

`.github/workflows/release.yml` builds the Windows installer and the Linux
binary on GitHub's own hosted runners — a Windows box for the `.msi`, a Linux
box for the other — and, when the trigger is a real version tag, publishes
both as a GitHub Release automatically. This is the easiest path since it
needs no Windows machine and no manual zip-and-copy step:

1. Push a version tag: `git tag v0.1.0 && git push origin v0.1.0`.
2. Watch the **Actions** tab on GitHub — `build-windows` and `build-linux` run
   in parallel, then `release` attaches both files to a new Release for that
   tag.
3. You (or anyone) downloads `ComplianceChecker.msi` or
   `compliance-checker-linux-x86_64.tar.gz` straight from the Release page.

The Windows job also submits the exe and the finished `.msi` to **SignPath
Foundation** for a real Authenticode signature — see "Code signing via
SignPath Foundation" below for the one-time setup this depends on. Until
that's configured, `build-windows` will get all the way through building the
`.msi` and then fail at the signing step, which is expected and still
confirms the rest of the pipeline works.

You can also trigger the workflow manually (Actions tab → Release → **Run
workflow**) without a tag — that builds both artifacts as a smoke test but
does **not** publish a Release, so it's safe to use to check the pipeline
still works before cutting a real version.

The rest of this file covers building either one by hand, useful for testing
a change before tagging a release.

## Building the Linux binary locally

Unlike Windows, this can be done directly on this VM (or any Linux box) since
PyInstaller doesn't need to cross-compile Linux-on-Linux:

```
cd frontend && npm install && npm run build && cd ..
python3.12 -m venv .venv && .venv/bin/pip install -e ".[desktop]"
.venv/bin/pyinstaller packaging/compliance-checker.spec
```

The finished binary lands at `dist/compliance-checker` — run it directly
(`chmod +x` first if needed) and it prints the URL and opens your browser to
it. This is the same `.spec` file used for Windows; which OS it targets
depends only on which OS runs `pyinstaller`.

## Building the Windows app by hand

This has to be built **on Windows itself** — PyInstaller bundles the actual
Python interpreter and native extensions for whatever OS you run it on, so a
Linux-built exe won't work on Windows and vice versa. These steps assume a
Windows machine with Python 3.12 and Node.js already installed.

### 1. Get the code onto the Windows machine

Copy (or `git clone`) the whole `compliance-checker` folder over from this
VM — the easiest path is probably the same VS Code file-download trick we
used for the GNS3 appliance file earlier, just for the whole folder (zip it
first, e.g. `zip -r compliance-checker.zip compliance-checker/` on this VM,
then download and unzip the archive on Windows).

### 2. Build the frontend

```
cd compliance-checker\frontend
npm install
npm run build
```

This produces `frontend\dist\` — the packaged app serves this directly, no
Vite dev server involved.

### 3. Set up the Python environment and install desktop dependencies

```
cd compliance-checker
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[desktop]"
```

That installs the app itself plus `pywebview` and `pyinstaller`.

### 4. Build the .exe

```
pyinstaller packaging\compliance-checker.spec
```

The finished executable lands at `dist\compliance-checker.exe`. You *can*
stop here and just run that file directly — but it won't show up in
Settings > Apps, won't have Start Menu shortcuts, and won't have a proper
uninstaller. For that, do step 5.

### 5. Build the .msi (adds Start Menu shortcut + uninstall support)

Install the [WiX Toolset](https://docs.firegiant.com/wix/) as a .NET tool
(needs the .NET SDK):

```
dotnet tool install --global wix --version 6.0.2
wix build packaging\compliance-checker.wxs -d SignedExeSource=dist\compliance-checker.exe -out ComplianceChecker.msi
```

(`SignedExeSource` just means "the exe to package" — building by hand like
this packages the *unsigned* exe from step 4, since only the CI pipeline has
access to the SignPath signing credentials. That's fine for testing an
install locally; it'll still show the same "Unknown Publisher" prompt an
unsigned build always does.)

This produces `ComplianceChecker.msi`. That installer:

- Installs to `%LOCALAPPDATA%\ComplianceChecker` — no admin rights or UAC
  prompt needed (`Scope="perUser"` in the `.wxs`)
- Adds a Start Menu shortcut
- Registers a normal uninstall entry under **Settings > Apps** (or Control
  Panel > Programs and Features) — no manual file cleanup needed later
- Leaves `%APPDATA%\ComplianceChecker\` (the database + credential
  encryption key) in place on uninstall, matching how most Windows apps
  handle user data — delete that folder by hand if you ever want a
  completely clean wipe

## Code signing via SignPath Foundation

The CI pipeline signs both the exe and the `.msi` using
[SignPath Foundation](https://signpath.org/), which signs qualifying
open-source projects for free (this repo qualifies: public, MIT-licensed, no
proprietary code). This is a one-time setup, done once by whoever maintains
the GitHub repo — not needed just to build locally:

1. Apply at signpath.org with this repo's URL and license info. Approval is
   a human-reviewed process, not instant (expect anywhere from days to a
   couple of weeks).
2. Once approved, in the SignPath dashboard: create a Project for this repo,
   a `release-signing` policy (used for real version-tag builds) and a
   `test-signing` policy (used for manual `workflow_dispatch` smoke-test
   runs), and register this GitHub repo as a Trusted Build System.
3. Generate a submitter-scoped API token, then in this GitHub repo go to
   **Settings → Secrets and variables → Actions** and add:
   - Secret `SIGNPATH_API_TOKEN` — the token from step 3
   - Variable `SIGNPATH_ORGANIZATION_ID` — your SignPath organization ID

Until this is done, `build-windows` still runs and still produces a real
(unsigned) `.msi` as a build artifact — it just fails at the two "Sign the
exe"/"Sign the msi" steps, which is the expected state for a repo that
hasn't completed SignPath onboarding yet.

## What happens on first run

- A per-user data folder is created automatically — `%APPDATA%\ComplianceChecker\`
  on Windows, `~/.compliance-checker/` on Linux — holding the SQLite database
  (and, on Windows, the encrypted credential key file; see below). Nothing
  needs to be configured by hand.
- **Windows**: the credential encryption key is generated on first run and
  protected with Windows DPAPI (`CryptProtectData`), tied to your specific
  Windows user account and machine — so even if someone copies the whole
  `ComplianceChecker` data folder elsewhere, the key file inside it is
  useless without also being logged in as you on this machine.
- **Linux**: the credential encryption key is generated on first run and
  stored directly in your OS keyring (Secret Service — GNOME Keyring or
  KWallet) via the `keyring` package, not as a file at all. This needs a real
  desktop session with a keyring daemon running (true of any normal Linux
  desktop). Before it even tries, a pre-flight check
  (`src/compliance_checker/linux_preflight.py`) probes whether a Secret
  Service is reachable at all; if not, it detects your package manager
  (apt/dnf/yum/pacman/zypper) and offers to install `gnome-keyring` for you —
  it only ever runs `sudo <package manager> install gnome-keyring` after you
  type `y` at a prompt in that same terminal, never silently. If there's no
  supported package manager, or you decline, or nothing's available to
  install (e.g. a headless box), it falls through to the real
  `keyring`-library error instead of a plaintext-file fallback — see
  "If something goes wrong" below.
- Either way, device credential *passwords* are encrypted with that key
  using Fernet (AES128-CBC + HMAC) before ever touching the database.
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
- **Antivirus/SmartScreen flags the install**: if you built it by hand
  locally (unsigned, per step 5 above), this is expected — PyInstaller
  binaries often get flagged since they're unfamiliar to reputation-based
  scanners, not because of anything in this codebase. The CI-built,
  SignPath-signed `.msi` shouldn't show the "Unknown Publisher" version of
  this warning, though SmartScreen's separate download-reputation prompt can
  still appear for a while on a brand new release until enough people have
  run it.
- **Linux: `keyring.errors.NoKeyringError` (or similar) on launch**: no
  Secret Service provider is running. The pre-flight check should already
  have offered to install `gnome-keyring` before this error ever shows up
  (see above) — if you declined it, it wasn't able to detect your package
  manager, or you're on a headless box with no login-session keyring to
  unlock, install/enable one yourself (`gnome-keyring` + a login-keyring
  unlock, or KWallet on KDE) and re-launch. Installing the daemon alone
  isn't always enough on a headless/SSH session specifically — it typically
  needs an actual graphical login to unlock. This is the one part of the
  Linux build that can't be fully verified from this VM (no desktop keyring
  session here) — same caveat as the untested Windows build below, just for
  the other platform.

Both `build-windows` and `build-linux` have completed successfully in CI
(GitHub's hosted runners), and the Linux binary has been smoke-tested
directly on this VM — but the WiX-built `.msi` and the SignPath signing
steps specifically are still new and haven't been exercised end-to-end yet
(signing needs the SignPath onboarding above to be finished first). Treat
the first real install attempt as a shakeout run, and paste back whatever
error comes up if it doesn't install/launch cleanly on the first try.

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
- **Credential encryption key**: auto-generated on first run. On Windows,
  stored (DPAPI-encrypted) at `%APPDATA%\ComplianceChecker\credential.key`;
  on Linux, stored directly in the OS keyring instead of a file at all. This
  protects stored device-credential passwords if the database file is copied
  elsewhere (e.g. into a synced cloud folder) — it does **not** protect against
  another process/user with access to the same account, since that's already
  inside the same trust boundary the OS itself defines via
  `%APPDATA%`.
- **No login screen on the app itself**: anyone who can launch the exe on
  your machine can use it — there's no separate password gate in front of
  the UI. Given this is a single-user desktop tool rather than a shared
  service, that's treated as acceptable for now; say the word if you want
  a PIN/password gate added, it'd be a real (if fairly small) feature
  addition, not a config flip.
- **Code signing**: CI-built releases are signed via SignPath Foundation (see
  "Code signing via SignPath Foundation" above) — both the exe and the
  `.msi`. Builds you produce by hand locally are unsigned, and will get the
  same SmartScreen/antivirus flagging any unsigned binary does (see the
  SmartScreen note above); that's expected for a local test build, not a
  sign of anything wrong.
