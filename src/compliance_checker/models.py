"""Validated contracts shared across the app."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Platform(str, Enum):
    CISCO_IOS = "cisco_ios"
    CISCO_NXOS = "cisco_nxos"
    ARISTA_EOS = "arista_eos"
    JUNIPER_JUNOS = "juniper_junos"


class Device(Model):
    id: str
    name: str
    management_address: str
    ssh_port: int = 22
    platform: Platform
    site: Optional[str] = None
    credential_profile_id: Optional[str] = None


class DeviceCreate(Model):
    name: str
    management_address: str
    ssh_port: int = 22
    platform: Platform
    site: Optional[str] = None
    credential_profile_id: Optional[str] = None


class ImportDevicesRequest(Model):
    devices: List[DeviceCreate]


class CredentialProfile(Model):
    id: str
    name: str
    username: str


class CredentialProfileCreate(Model):
    name: str
    username: str
    password: str


class CredentialProfileUpdate(Model):
    name: str
    username: str
    password: Optional[str] = None  # omit to keep the existing password


class Site(Model):
    id: str
    name: str


class SiteCreate(Model):
    name: str


class DiscoveredHost(Model):
    address: str
    reachable: bool
    auth_ok: bool
    guessed_platform: Optional[Platform] = None
    guessed_hostname: Optional[str] = None


class ScanRequest(Model):
    range: str
    credential_profile_id: str
    port: int = 22


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Rule(Model):
    id: str
    description: str
    severity: Severity
    require: List[str] = []
    forbid: List[str] = []
    platforms: List[Platform] = []  # empty means all platforms
    applies_if: List[str] = []  # regexes; rule only evaluated if any match the config (empty means always)
    applies_if_label: Optional[str] = None  # human-readable form of applies_if, filled in by rule_loader
    notes: Optional[str] = None  # implementation caveats: platform dependencies, engine limitations, etc.
    fix: Optional[str] = None  # example CLI commands to remediate a failure


class RuleStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class RuleResult(Model):
    rule_id: str
    status: RuleStatus
    evidence: List[str] = []
    override_comment: Optional[str] = None


class ResultOverride(Model):
    device_id: str
    rule_id: str
    comment: str
    created_at: datetime


class ResultOverrideCreate(Model):
    comment: str


class DeviceCheckResult(Model):
    device_id: str
    device_name: str
    checked_at: datetime
    rule_results: List[RuleResult]
    collection_error: Optional[str] = None

    @property
    def passed(self) -> int:
        return sum(1 for r in self.rule_results if r.status == RuleStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.rule_results if r.status == RuleStatus.FAIL)


class ComplianceRun(Model):
    id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    device_results: List[DeviceCheckResult] = []


class RuleChange(Model):
    rule_id: str
    previous_status: Optional[RuleStatus] = None  # None means the rule is new since the last run
    current_status: Optional[RuleStatus] = None  # None means the rule no longer applies


class DeviceChanges(Model):
    device_id: str
    previous_checked_at: Optional[datetime] = None  # None means there's no earlier run to compare
    current_checked_at: datetime
    changes: List[RuleChange] = []


class ScheduleSettings(Model):
    enabled: bool = False
    interval_hours: int = 24
