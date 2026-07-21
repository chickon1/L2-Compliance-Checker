"""SQLite persistence for runs/results, devices, credential profiles, and sites."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .credentials import Credentials, decrypt_secret, encrypt_secret
from .models import (
    ComplianceRun,
    CredentialProfile,
    Device,
    DeviceCheckResult,
    Platform,
    ResultOverride,
    RuleResult,
    ScheduleSettings,
    Site,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS device_results (
    run_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    device_name TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    rule_results TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    management_address TEXT NOT NULL,
    ssh_port INTEGER NOT NULL,
    platform TEXT NOT NULL,
    site TEXT,
    credential_profile_id TEXT
);

CREATE TABLE IF NOT EXISTS credential_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT NOT NULL,
    encrypted_password BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS sites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS result_overrides (
    device_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    comment TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (device_id, rule_id)
);

CREATE TABLE IF NOT EXISTS schedule_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    interval_hours INTEGER NOT NULL DEFAULT 24
);
"""


class Repository:
    def __init__(self, db_path: str, credential_key: Optional[str] = None) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._credential_key = credential_key

    # Runs / results

    def start_run(self, run_id: str, started_at: datetime) -> None:
        self._conn.execute(
            "INSERT INTO runs (id, started_at) VALUES (?, ?)",
            (run_id, started_at.isoformat()),
        )
        self._conn.commit()

    def finish_run(
        self, run_id: str, finished_at: datetime, device_results: List[DeviceCheckResult]
    ) -> None:
        self._conn.execute(
            "UPDATE runs SET finished_at = ? WHERE id = ?",
            (finished_at.isoformat(), run_id),
        )
        for result in device_results:
            self._conn.execute(
                """INSERT INTO device_results
                   (run_id, device_id, device_name, checked_at, rule_results)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    run_id,
                    result.device_id,
                    result.device_name,
                    result.checked_at.isoformat(),
                    json.dumps([r.model_dump(mode="json") for r in result.rule_results]),
                ),
            )
        self._conn.commit()

    def latest_run(self) -> Optional[ComplianceRun]:
        row = self._conn.execute(
            "SELECT id, started_at, finished_at FROM runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        run_id, started_at, finished_at = row
        return self._run_with_results(run_id, started_at, finished_at)

    def latest_device_result(self, device_id: str) -> Optional[tuple[str, DeviceCheckResult]]:
        row = self._conn.execute(
            """SELECT dr.run_id, dr.device_name, dr.checked_at, dr.rule_results
               FROM device_results dr JOIN runs r ON dr.run_id = r.id
               WHERE dr.device_id = ?
               ORDER BY r.started_at DESC LIMIT 1""",
            (device_id,),
        ).fetchone()
        if row is None:
            return None
        run_id, device_name, checked_at, rule_results = row
        return run_id, DeviceCheckResult(
            device_id=device_id,
            device_name=device_name,
            checked_at=checked_at,
            rule_results=[RuleResult.model_validate(r) for r in json.loads(rule_results)],
        )

    def previous_device_result(
        self, device_id: str, exclude_run_id: str
    ) -> Optional[DeviceCheckResult]:
        row = self._conn.execute(
            """SELECT dr.device_name, dr.checked_at, dr.rule_results
               FROM device_results dr JOIN runs r ON dr.run_id = r.id
               WHERE dr.device_id = ? AND dr.run_id != ?
               ORDER BY r.started_at DESC LIMIT 1""",
            (device_id, exclude_run_id),
        ).fetchone()
        if row is None:
            return None
        device_name, checked_at, rule_results = row
        return DeviceCheckResult(
            device_id=device_id,
            device_name=device_name,
            checked_at=checked_at,
            rule_results=[RuleResult.model_validate(r) for r in json.loads(rule_results)],
        )

    def get_run(self, run_id: str) -> Optional[ComplianceRun]:
        row = self._conn.execute(
            "SELECT id, started_at, finished_at FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return self._run_with_results(*row)

    def _run_with_results(
        self, run_id: str, started_at: str, finished_at: Optional[str]
    ) -> ComplianceRun:
        rows = self._conn.execute(
            """SELECT device_id, device_name, checked_at, rule_results
               FROM device_results WHERE run_id = ?""",
            (run_id,),
        ).fetchall()
        device_results = [
            DeviceCheckResult(
                device_id=device_id,
                device_name=device_name,
                checked_at=checked_at,
                rule_results=[RuleResult.model_validate(r) for r in json.loads(rule_results)],
            )
            for device_id, device_name, checked_at, rule_results in rows
        ]
        return ComplianceRun(
            id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            device_results=device_results,
        )

    # Devices

    def add_device(self, device: Device) -> None:
        self._insert_device(device)
        self._conn.commit()

    def add_devices(self, devices: List[Device]) -> None:
        for device in devices:
            self._insert_device(device)
        self._conn.commit()

    def _insert_device(self, device: Device) -> None:
        self._conn.execute(
            """INSERT INTO devices
               (id, name, management_address, ssh_port, platform, site, credential_profile_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                device.id,
                device.name,
                device.management_address,
                device.ssh_port,
                device.platform.value,
                device.site,
                device.credential_profile_id,
            ),
        )

    def list_devices(self) -> List[Device]:
        rows = self._conn.execute(
            """SELECT id, name, management_address, ssh_port, platform, site,
                      credential_profile_id
               FROM devices"""
        ).fetchall()
        return [
            Device(
                id=r[0],
                name=r[1],
                management_address=r[2],
                ssh_port=r[3],
                platform=Platform(r[4]),
                site=r[5],
                credential_profile_id=r[6],
            )
            for r in rows
        ]

    def get_device(self, device_id: str) -> Device:
        for device in self.list_devices():
            if device.id == device_id:
                return device
        raise KeyError(device_id)

    def update_device(self, device: Device) -> None:
        cursor = self._conn.execute(
            """UPDATE devices
               SET name = ?, management_address = ?, ssh_port = ?, platform = ?,
                   site = ?, credential_profile_id = ?
               WHERE id = ?""",
            (
                device.name,
                device.management_address,
                device.ssh_port,
                device.platform.value,
                device.site,
                device.credential_profile_id,
                device.id,
            ),
        )
        if cursor.rowcount == 0:
            raise KeyError(device.id)
        self._conn.commit()

    def delete_device(self, device_id: str) -> None:
        cursor = self._conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        if cursor.rowcount == 0:
            raise KeyError(device_id)
        self._conn.execute("DELETE FROM result_overrides WHERE device_id = ?", (device_id,))
        self._conn.commit()

    # Credential profiles

    def add_credential_profile(self, profile: CredentialProfile, password: str) -> None:
        if not self._credential_key:
            raise RuntimeError("CC_CREDENTIAL_KEY must be set to store credential profiles")
        encrypted = encrypt_secret(self._credential_key, password)
        self._conn.execute(
            """INSERT INTO credential_profiles (id, name, username, encrypted_password)
               VALUES (?, ?, ?, ?)""",
            (profile.id, profile.name, profile.username, encrypted),
        )
        self._conn.commit()

    def list_credential_profiles(self) -> List[CredentialProfile]:
        rows = self._conn.execute(
            "SELECT id, name, username FROM credential_profiles"
        ).fetchall()
        return [CredentialProfile(id=r[0], name=r[1], username=r[2]) for r in rows]

    def update_credential_profile(
        self, profile_id: str, name: str, username: str, password: Optional[str]
    ) -> None:
        if password is not None:
            if not self._credential_key:
                raise RuntimeError("CC_CREDENTIAL_KEY must be set to store credential profiles")
            encrypted = encrypt_secret(self._credential_key, password)
            cursor = self._conn.execute(
                """UPDATE credential_profiles
                   SET name = ?, username = ?, encrypted_password = ? WHERE id = ?""",
                (name, username, encrypted, profile_id),
            )
        else:
            cursor = self._conn.execute(
                "UPDATE credential_profiles SET name = ?, username = ? WHERE id = ?",
                (name, username, profile_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(profile_id)
        self._conn.commit()

    def delete_credential_profile(self, profile_id: str) -> None:
        cursor = self._conn.execute(
            "DELETE FROM credential_profiles WHERE id = ?", (profile_id,)
        )
        if cursor.rowcount == 0:
            raise KeyError(profile_id)
        self._conn.commit()

    def get_credentials(self, profile_id: str) -> Credentials:
        if not self._credential_key:
            raise RuntimeError("CC_CREDENTIAL_KEY must be set to read credential profiles")
        row = self._conn.execute(
            "SELECT username, encrypted_password FROM credential_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if row is None:
            raise KeyError(profile_id)
        username, encrypted_password = row
        return Credentials(
            username=username,
            password=decrypt_secret(self._credential_key, encrypted_password),
        )

    # Sites

    def add_site(self, site: Site) -> None:
        self._conn.execute("INSERT INTO sites (id, name) VALUES (?, ?)", (site.id, site.name))
        self._conn.commit()

    def list_sites(self) -> List[Site]:
        rows = self._conn.execute("SELECT id, name FROM sites").fetchall()
        return [Site(id=r[0], name=r[1]) for r in rows]

    def get_site_by_name(self, name: str) -> Optional[Site]:
        row = self._conn.execute("SELECT id, name FROM sites WHERE name = ?", (name,)).fetchone()
        return Site(id=row[0], name=row[1]) if row else None

    # Result overrides ("not applicable" markings)

    def set_override(
        self, device_id: str, rule_id: str, comment: str, created_at: datetime
    ) -> None:
        self._conn.execute(
            """INSERT INTO result_overrides (device_id, rule_id, comment, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (device_id, rule_id)
               DO UPDATE SET comment = excluded.comment, created_at = excluded.created_at""",
            (device_id, rule_id, comment, created_at.isoformat()),
        )
        self._conn.commit()

    def clear_override(self, device_id: str, rule_id: str) -> None:
        self._conn.execute(
            "DELETE FROM result_overrides WHERE device_id = ? AND rule_id = ?",
            (device_id, rule_id),
        )
        self._conn.commit()

    def get_overrides_by_device(self, device_id: str) -> dict[str, ResultOverride]:
        rows = self._conn.execute(
            "SELECT rule_id, comment, created_at FROM result_overrides WHERE device_id = ?",
            (device_id,),
        ).fetchall()
        return {
            rule_id: ResultOverride(
                device_id=device_id, rule_id=rule_id, comment=comment, created_at=created_at
            )
            for rule_id, comment, created_at in rows
        }

    # Schedule settings

    def get_schedule_settings(self) -> ScheduleSettings:
        row = self._conn.execute(
            "SELECT enabled, interval_hours FROM schedule_settings WHERE id = 1"
        ).fetchone()
        if row is None:
            return ScheduleSettings()
        enabled, interval_hours = row
        return ScheduleSettings(enabled=bool(enabled), interval_hours=interval_hours)

    def set_schedule_settings(self, settings: ScheduleSettings) -> None:
        self._conn.execute(
            """INSERT INTO schedule_settings (id, enabled, interval_hours) VALUES (1, ?, ?)
               ON CONFLICT (id) DO UPDATE SET enabled = excluded.enabled,
                                               interval_hours = excluded.interval_hours""",
            (int(settings.enabled), settings.interval_hours),
        )
        self._conn.commit()
