"""Orchestrates compliance runs, device inventory, discovery, and credential profiles."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from .collectors.discovery import detect_platform, scan_range
from .collectors.ssh import ConfigCollector
from .models import (
    ComplianceRun,
    CredentialProfile,
    CredentialProfileCreate,
    CredentialProfileUpdate,
    Device,
    DeviceChanges,
    DeviceCheckResult,
    DeviceCreate,
    DiscoveredHost,
    ResultOverride,
    Rule,
    RuleChange,
    RuleResult,
    RuleStatus,
    Site,
    SiteCreate,
)
from .repository import Repository
from .rule_engine import evaluate_all


def _applicable_rules(rules: List[Rule], device: Device, raw_config: str) -> List[Rule]:
    return [
        rule
        for rule in rules
        if (not rule.platforms or device.platform in rule.platforms)
        and (not rule.applies_if or any(re.search(p, raw_config) for p in rule.applies_if))
    ]


def _apply_overrides(
    rule_results: List[RuleResult], overrides: dict[str, ResultOverride]
) -> List[RuleResult]:
    applied = []
    for result in rule_results:
        override = overrides.get(result.rule_id)
        if result.status == RuleStatus.FAIL and override is not None:
            result = result.model_copy(
                update={"status": RuleStatus.NOT_APPLICABLE, "override_comment": override.comment}
            )
        applied.append(result)
    return applied


def _diff_results(
    previous: Optional[List[RuleResult]], current: List[RuleResult]
) -> List[RuleChange]:
    previous_by_id = {r.rule_id: r.status for r in (previous or [])}
    current_by_id = {r.rule_id: r.status for r in current}
    changed_ids = {
        rule_id
        for rule_id in set(previous_by_id) | set(current_by_id)
        if previous_by_id.get(rule_id) != current_by_id.get(rule_id)
    }
    return [
        RuleChange(
            rule_id=rule_id,
            previous_status=previous_by_id.get(rule_id),
            current_status=current_by_id.get(rule_id),
        )
        for rule_id in sorted(changed_ids)
    ]


class ComplianceService:
    def __init__(
        self,
        collector: ConfigCollector,
        rules: List[Rule],
        repository: Repository,
    ) -> None:
        self._collector = collector
        self._rules = rules
        self._repository = repository

    def rules(self) -> List[Rule]:
        return self._rules

    # Devices

    def devices(self) -> List[Device]:
        return self._repository.list_devices()

    def import_devices(self, device_creates: List[DeviceCreate]) -> List[Device]:
        devices = [Device(id=str(uuid.uuid4()), **dc.model_dump()) for dc in device_creates]
        self._repository.add_devices(devices)
        return devices

    def update_device(self, device_id: str, update: DeviceCreate) -> Device:
        device = Device(id=device_id, **update.model_dump())
        self._repository.update_device(device)
        return device

    def delete_device(self, device_id: str) -> None:
        self._repository.delete_device(device_id)

    def run(self, device_ids: Optional[List[str]] = None) -> ComplianceRun:
        all_devices = {d.id: d for d in self._repository.list_devices()}
        devices = (
            [all_devices[d] for d in device_ids] if device_ids else list(all_devices.values())
        )

        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        self._repository.start_run(run_id, started_at)

        device_results: List[DeviceCheckResult] = []
        for device in devices:
            try:
                credentials = (
                    self._repository.get_credentials(device.credential_profile_id)
                    if device.credential_profile_id
                    else None
                )
                collected = self._collector.collect(device, credentials)
            except Exception as exc:  # noqa: BLE001 - one bad device must not abort the batch
                device_results.append(
                    DeviceCheckResult(
                        device_id=device.id,
                        device_name=device.name,
                        checked_at=datetime.now(timezone.utc),
                        rule_results=[],
                        collection_error=str(exc),
                    )
                )
                continue

            applicable_rules = _applicable_rules(self._rules, device, collected.raw_config)
            rule_results = evaluate_all(applicable_rules, collected.raw_config)
            overrides = self._repository.get_overrides_by_device(device.id)
            rule_results = _apply_overrides(rule_results, overrides)
            device_results.append(
                DeviceCheckResult(
                    device_id=device.id,
                    device_name=device.name,
                    checked_at=collected.collected_at,
                    rule_results=rule_results,
                )
            )

        finished_at = datetime.now(timezone.utc)
        self._repository.finish_run(run_id, finished_at, device_results)

        return ComplianceRun(
            id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            device_results=device_results,
        )

    def latest_run(self) -> Optional[ComplianceRun]:
        return self._repository.latest_run()

    def changes_for_device(self, device_id: str) -> Optional[DeviceChanges]:
        latest = self._repository.latest_device_result(device_id)
        if latest is None:
            return None
        current_run_id, current_result = latest
        previous_result = self._repository.previous_device_result(device_id, current_run_id)
        if previous_result is None:
            return DeviceChanges(
                device_id=device_id,
                previous_checked_at=None,
                current_checked_at=current_result.checked_at,
                changes=[],
            )
        return DeviceChanges(
            device_id=device_id,
            previous_checked_at=previous_result.checked_at,
            current_checked_at=current_result.checked_at,
            changes=_diff_results(previous_result.rule_results, current_result.rule_results),
        )

    def create_override(self, device_id: str, rule_id: str, comment: str) -> ResultOverride:
        created_at = datetime.now(timezone.utc)
        self._repository.set_override(device_id, rule_id, comment, created_at)
        return ResultOverride(
            device_id=device_id, rule_id=rule_id, comment=comment, created_at=created_at
        )

    def clear_override(self, device_id: str, rule_id: str) -> None:
        self._repository.clear_override(device_id, rule_id)

    # Credential profiles

    def list_credential_profiles(self) -> List[CredentialProfile]:
        return self._repository.list_credential_profiles()

    def create_credential_profile(self, create: CredentialProfileCreate) -> CredentialProfile:
        profile = CredentialProfile(id=str(uuid.uuid4()), name=create.name, username=create.username)
        self._repository.add_credential_profile(profile, create.password)
        return profile

    def update_credential_profile(
        self, profile_id: str, update: CredentialProfileUpdate
    ) -> CredentialProfile:
        self._repository.update_credential_profile(
            profile_id, update.name, update.username, update.password
        )
        return CredentialProfile(id=profile_id, name=update.name, username=update.username)

    def delete_credential_profile(self, profile_id: str) -> None:
        self._repository.delete_credential_profile(profile_id)

    # Sites

    def list_sites(self) -> List[Site]:
        return self._repository.list_sites()

    def create_site(self, create: SiteCreate) -> Site:
        existing = self._repository.get_site_by_name(create.name)
        if existing:
            return existing
        site = Site(id=str(uuid.uuid4()), name=create.name)
        self._repository.add_site(site)
        return site

    # Discovery

    def scan(self, range_str: str, credential_profile_id: str, port: int = 22) -> List[DiscoveredHost]:
        credentials = self._repository.get_credentials(credential_profile_id)
        open_addresses = scan_range(range_str, port)
        return [detect_platform(address, port, credentials) for address in open_addresses]
