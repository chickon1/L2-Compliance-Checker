# Compliance Checker

Compliance Checker pulls running-config from lab network devices over SSH and
evaluates it against a human-editable set of YAML rules, showing pass/fail
per device and per rule in the browser.

This is a separate app from L2Workbench: separate codebase, separate port
(8444 backend / 5173 frontend dev server, vs. L2Workbench's 8443), and no
shared code. It targets the GNS3 lab on `192.168.100.0/24`.

## Development

Runtime is Rocky Linux 9 with Python 3.12. Create a local virtual environment
and install the declared dependencies, then run the backend tests:

```text
python3.12 -m venv .venv
.venv/bin/pip install -e ".[test]"
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Devices and credential profiles live in the SQLite DB (`CC_DB_PATH`), not a
static file — use the app's Import page to scan an address range and bulk-add
devices (`platform` will be one of `cisco_ios`, `cisco_nxos`, `arista_eos`).
Credential profile passwords are Fernet-encrypted at rest; the encryption key
is supplied separately via `CC_CREDENTIAL_KEY` and must never be stored
beside the database or committed.

Relevant configuration variables:

```text
CC_PORT=8444
CC_CREDENTIAL_KEY=<Fernet key>
CC_RULES_DIR=src/compliance_checker/rules
CC_DB_PATH=data/compliance_checker.db
```

The production factory requires `CC_CREDENTIAL_KEY` and starts with an empty
device inventory — populate it via the Import page (Discovery scan + bulk
import). Run it with:

```text
PYTHONPATH=src .venv/bin/uvicorn --factory compliance_checker.bootstrap:create_application --host 0.0.0.0 --port 8444
```

For frontend/rule-engine work without the GNS3 lab powered on, run the mock
factory instead — it serves a canned sample config rather than SSHing out:

```text
PYTHONPATH=src .venv/bin/uvicorn --factory compliance_checker.bootstrap:create_mock_application --host 127.0.0.1 --port 8444
```

### Frontend

```text
cd frontend
npm install
npm run dev       # http://localhost:5173, proxies /api to 127.0.0.1:8444
npm run typecheck
npm run test
```

### Rule packs

Rule packs live in `src/compliance_checker/rules/*.yaml`. Each rule has an
`id`, `description`, `severity`, and `require`/`forbid` lists of regexes
checked against the full running-config text. `baseline.yaml` is a starting
template — edit it or add more `.yaml` files in the same directory.

### Adding devices

Use the Import page: create a credential profile (username/password, stored
encrypted), enter an address range (CIDR like `192.168.100.0/24` or a
short-form range like `192.168.100.1-20`), and scan. Reachable hosts are
probed with that credential profile to guess platform and read back the
device's own configured hostname; review/edit the results (name, platform,
site) and add the ones you want to the inventory.
