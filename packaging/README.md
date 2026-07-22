# Building the standalone Linux build (and the Windows app by hand)

This turns the compliance-checker web app into a single executable that runs
entirely on your own machine.

- **Linux**: `compliance-checker` runs the server and opens it in your normal
  browser (`http://127.0.0.1:8444`) — same experience as running the app
  in dev, just as one binary instead of a venv + `npm run build` + `uvicorn`.
  This is the one built and published via CI.
- **Windows**: `compliance-checker.exe` opens in its own native window
  (pywebview) — no browser tab, no separate server process to remember to
  start. Not currently built/published via CI (see note below) — build it by
  hand if you want to try it.

## Recommended: let GitHub Actions build the Linux binary

`.github/workflows/release.yml` builds the Linux binary on GitHub's own
hosted runner and, when the trigger is a real version tag, publishes it as a
GitHub Release automatically:

1. Push a version tag: `git tag v0.1.0 && git push origin v0.1.0`.
2. Watch the **Actions** tab on GitHub — `build-linux` runs, then `release`
   attaches two files to a new Release for that tag.
3. You (or anyone) downloads either straight from the Release page:
   - `compliance-checker-linux-x86_64.tar.gz` — the raw binary, works on any
     Linux distro, no package manager involved (untar, `chmod +x`, run).
   - `compliance-checker-linux-x86_64.rpm` — for RPM-based distros (Rocky,
     Fedora, RHEL — i.e. this VM). Installs to `/usr/bin/compliance-checker`,
     shows up in `dnf list installed`, and uninstalls cleanly with
     `sudo dnf remove compliance-checker`.

You can also trigger the workflow manually (Actions tab → Release → **Run
workflow**) without a tag — that builds the artifact as a smoke test but
does **not** publish a Release, so it's safe to use to check the pipeline
still works before cutting a real version.

**About Windows**: a CI-built, signed `.msi` (via WiX Toolset + SignPath
Foundation) was set up and worked right up to the signing step, which needs
a completed SignPath Foundation application (free for open-source projects,
but a human-reviewed process, not instant). That got shelved for now to keep
things simple — see the "Switch Windows packaging to a signed MSI" commit in
git history if picking it back up later. In the meantime, the Windows app
still exists and can be built by hand (below); it just won't be signed or
published automatically.

## Building the Linux binary locally

This can be done directly on this VM (or any Linux box) since PyInstaller
doesn't need to cross-compile Linux-on-Linux:

```
cd frontend && npm install && npm run build && cd ..
python3.12 -m venv .venv && .venv/bin/pip install -e ".[desktop]"
.venv/bin/pyinstaller packaging/compliance-checker.spec
```

The finished binary lands at `dist/compliance-checker` — run it directly
(`chmod +x` first if needed) and it prints the URL and opens your browser to
it.

### Wrapping it as an .rpm

Optional — only needed if you want a real installable package (`dnf install`,
shows up in `dnf list installed`, clean `dnf remove` uninstall) instead of
just running the raw binary. Uses [fpm](https://fpm.readthedocs.io/), which
avoids hand-writing an RPM `.spec` file:

```
sudo dnf install -y rpm-build ruby
sudo gem install --no-document fpm
fpm -s dir -t rpm \
  --name compliance-checker \
  --version 0.1.0 \
  --license MIT \
  --architecture x86_64 \
  --description "Network gear STIG compliance checker" \
  --url "https://github.com/chickon1/L2-Compliance-Checker" \
  --package compliance-checker-linux-x86_64.rpm \
  dist/compliance-checker=/usr/bin/compliance-checker
```

That produces `compliance-checker-linux-x86_64.rpm`, installing the binary
to `/usr/bin/compliance-checker`. The CI pipeline does the same thing (on
Ubuntu, where the equivalent package is `rpm` rather than `rpm-build`) and
attaches the result to each GitHub Release.

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

The finished executable lands at `dist\compliance-checker.exe` — run it
directly. There's currently no installer step (that was the WiX/SignPath
piece that got shelved — see above); this is just the standalone exe, so it
won't show up in Settings > Apps or have Start Menu shortcuts, and Windows
will flag it as an unsigned/unknown-publisher executable the first time it
runs (expected for any unsigned build, not a sign of a problem).

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
- **Antivirus/SmartScreen flags the .exe**: expected for an unsigned,
  freshly-built executable — PyInstaller binaries often get flagged since
  they're unfamiliar to reputation-based scanners, not because of anything
  in this codebase. Code-signing would fix this longer-term (see the WiX/
  SignPath note above) but isn't currently set up.
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
  session here).

`build-linux` has completed successfully in CI (GitHub's hosted runner), and
the binary has also been smoke-tested directly on this VM. The Windows exe
hasn't been run on a real Windows machine at all yet — treat the first
attempt as a shakeout run, and paste back whatever error comes up if it
doesn't launch cleanly on the first try.

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
- **Unsigned executable**: no code-signing certificate is set up currently
  (see the WiX/SignPath note above), so Windows SmartScreen/antivirus will
  likely flag a fresh build the first time it runs. This is normal for
  unsigned binaries and isn't indicative of anything wrong with the build.
