import tempfile
import unittest
from pathlib import Path

from compliance_checker.collectors.ssh import CollectedConfig
from compliance_checker.models import Device, Platform, Rule, ScheduleSettings, Severity
from compliance_checker.repository import Repository
from compliance_checker.scheduler import ComplianceScheduler
from compliance_checker.service import ComplianceService


class ConfigSequenceCollector:
    """Returns a different raw_config on each successive collect() call."""

    def __init__(self, configs):
        self._configs = iter(configs)

    def collect(self, device, credentials):
        from datetime import datetime, timezone

        return CollectedConfig(
            device_id=device.id,
            collected_at=datetime.now(timezone.utc),
            raw_config=next(self._configs),
        )


class ChangesSinceLastRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))
        self.device = Device(
            id="sw1", name="sw1", management_address="10.0.0.1", platform=Platform.CISCO_IOS
        )
        self.repository.add_device(self.device)
        self.rules = [
            Rule(
                id="banner-present",
                description="banner must be set",
                severity=Severity.LOW,
                require=["banner motd"],
            )
        ]

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_no_previous_run_returns_empty_changes(self) -> None:
        service = ComplianceService(
            ConfigSequenceCollector(["hostname x"]), self.rules, self.repository
        )
        service.run()

        changes = service.changes_for_device("sw1")

        self.assertIsNotNone(changes)
        self.assertIsNone(changes.previous_checked_at)
        self.assertEqual(changes.changes, [])

    def test_status_flip_is_reported_as_a_change(self) -> None:
        collector = ConfigSequenceCollector(["hostname x", "hostname x\nbanner motd\n"])
        service = ComplianceService(collector, self.rules, self.repository)

        service.run()  # fails: no banner
        service.run()  # passes: banner now present

        changes = service.changes_for_device("sw1")

        self.assertIsNotNone(changes)
        self.assertIsNotNone(changes.previous_checked_at)
        self.assertEqual(len(changes.changes), 1)
        change = changes.changes[0]
        self.assertEqual(change.rule_id, "banner-present")
        self.assertEqual(change.previous_status, "fail")
        self.assertEqual(change.current_status, "pass")

    def test_unchanged_rule_does_not_appear_in_diff(self) -> None:
        collector = ConfigSequenceCollector(["hostname x", "hostname x"])
        service = ComplianceService(collector, self.rules, self.repository)

        service.run()
        service.run()

        changes = service.changes_for_device("sw1")
        self.assertEqual(changes.changes, [])

    def test_unknown_device_returns_none(self) -> None:
        service = ComplianceService(ConfigSequenceCollector([]), self.rules, self.repository)
        self.assertIsNone(service.changes_for_device("does-not-exist"))


class ScheduleSettingsRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_defaults_when_never_set(self) -> None:
        settings = self.repository.get_schedule_settings()
        self.assertFalse(settings.enabled)
        self.assertEqual(settings.interval_hours, 24)

    def test_round_trip(self) -> None:
        self.repository.set_schedule_settings(ScheduleSettings(enabled=True, interval_hours=6))
        settings = self.repository.get_schedule_settings()
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.interval_hours, 6)

    def test_update_overwrites_previous_value(self) -> None:
        self.repository.set_schedule_settings(ScheduleSettings(enabled=True, interval_hours=6))
        self.repository.set_schedule_settings(ScheduleSettings(enabled=False, interval_hours=12))
        settings = self.repository.get_schedule_settings()
        self.assertFalse(settings.enabled)
        self.assertEqual(settings.interval_hours, 12)


class ComplianceSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))
        self.service = ComplianceService(ConfigSequenceCollector([]), [], self.repository)
        self.scheduler = ComplianceScheduler(self.service, self.repository)

    def tearDown(self) -> None:
        self.scheduler.shutdown()
        self._tmpdir.cleanup()

    def test_disabled_by_default_no_job_registered(self) -> None:
        self.assertIsNone(self.scheduler._scheduler.get_job("compliance-scheduled-run"))

    def test_enabling_registers_a_job(self) -> None:
        self.scheduler.update_settings(ScheduleSettings(enabled=True, interval_hours=6))
        job = self.scheduler._scheduler.get_job("compliance-scheduled-run")
        self.assertIsNotNone(job)

    def test_disabling_removes_the_job(self) -> None:
        self.scheduler.update_settings(ScheduleSettings(enabled=True, interval_hours=6))
        self.scheduler.update_settings(ScheduleSettings(enabled=False, interval_hours=6))
        job = self.scheduler._scheduler.get_job("compliance-scheduled-run")
        self.assertIsNone(job)

    def test_settings_persist_to_repository(self) -> None:
        self.scheduler.update_settings(ScheduleSettings(enabled=True, interval_hours=8))
        self.assertEqual(
            self.repository.get_schedule_settings(),
            ScheduleSettings(enabled=True, interval_hours=8),
        )


if __name__ == "__main__":
    unittest.main()
