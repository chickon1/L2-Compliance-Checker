# Compliance Checker

Pulls running-config from lab devices over SSH and evaluates it against
YAML-defined compliance rules; shows pass/fail per device/rule in the UI.

## Boundaries

- Separate codebase and port from L2Workbench (`/opt/l2workbench`, port 8443).
  Never edit, run, or stop anything under `/opt/l2workbench` while working on
  this project. L2Workbench's compliance module was reviewed as prior art but
  deliberately **not** reused — this app is built fresh.
- Backend: FastAPI + Pydantic, port 8444. Frontend: React + TypeScript + Vite,
  dev server on port 5173 (proxies `/api` to 127.0.0.1:8444).
- Target lab: GNS3, `192.168.100.0/24`.

## Stack notes

- Config collection uses Netmiko (`src/compliance_checker/collectors/ssh.py`),
  keyed by `Platform` (`cisco_ios`, `cisco_nxos`, `arista_eos`).
- A `MockConfigCollector` (`collectors/mock.py`) and `create_mock_application`
  factory let the rule engine and frontend be developed without the lab
  powered on.
- Rules are flat regex `require`/`forbid` checks over the full config text
  (`rule_engine.py`), loaded from YAML packs in `rules/` — no per-section or
  per-interface parsing yet.
- Everything persists to one SQLite DB via `repository.py` (stdlib `sqlite3`,
  no ORM): runs/results, devices, credential profiles (Fernet-encrypted
  passwords, key from `CC_CREDENTIAL_KEY`), and sites. There is no static
  device or credential file anymore — devices come from the Import page's
  discovery scan + bulk import flow (`collectors/discovery.py`:
  `scan_range` does a TCP port sweep over a CIDR or start-end range,
  `detect_platform` uses Netmiko's `SSHDetect` plus `find_prompt()` to guess
  platform and read the device's real configured hostname).
- The mock factory seeds two example devices at startup for convenience; the
  real factory starts with an empty inventory on purpose.

## Known infra note

This VM's outbound-facing ports need two separate firewall layers opened:
firewalld on the VM itself, and a network-level firewall/security group in
front of it that only allows a few ports through by default (22, 8443 were
already open; 5173 was not and needed the upstream layer opened too, which
Claude cannot access or configure). If a new port stops being reachable from
outside the VM after it works locally (`curl` succeeds on the VM, browser
times out), check both layers before assuming an app bug.
