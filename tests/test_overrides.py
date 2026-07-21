import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from compliance_checker.collectors.ssh import CollectedConfig
from compliance_checker.models import Device, Platform, Rule, RuleStatus, Severity
from compliance_checker.repository import Repository
from compliance_checker.service import ComplianceService


class ConfigByDeviceCollector:
    def __init__(self, config_by_device_id):
        self._config_by_device_id = config_by_device_id

    def collect(self, device, credentials):
        return CollectedConfig(
            device_id=device.id,
            collected_at=datetime.now(timezone.utc),
            raw_config=self._config_by_device_id[device.id],
        )


class RepositoryOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_set_get_clear_round_trip(self) -> None:
        self.repository.set_override("dev1", "rule1", "not applicable here", datetime.now(timezone.utc))

        overrides = self.repository.get_overrides_by_device("dev1")
        self.assertEqual(set(overrides.keys()), {"rule1"})
        self.assertEqual(overrides["rule1"].comment, "not applicable here")

        self.repository.clear_override("dev1", "rule1")
        self.assertEqual(self.repository.get_overrides_by_device("dev1"), {})

    def test_setting_again_replaces_comment(self) -> None:
        self.repository.set_override("dev1", "rule1", "first reason", datetime.now(timezone.utc))
        self.repository.set_override("dev1", "rule1", "updated reason", datetime.now(timezone.utc))

        overrides = self.repository.get_overrides_by_device("dev1")
        self.assertEqual(overrides["rule1"].comment, "updated reason")


class ServiceOverrideApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))

        self.device = Device(
            id="dev1", name="dev1", management_address="10.0.0.1", platform=Platform.ARISTA_EOS
        )
        self.repository.add_devices([self.device])

        self.rules = [
            Rule(
                id="failing-rule",
                description="Always fails against this config",
                severity=Severity.HIGH,
                require=["nonexistent-pattern"],
            ),
            Rule(
                id="passing-rule",
                description="Always passes against this config",
                severity=Severity.LOW,
                require=["hostname"],
            ),
        ]
        collector = ConfigByDeviceCollector({"dev1": "hostname dev1\n"})
        self.service = ComplianceService(collector, self.rules, self.repository)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _result_for(self, run, rule_id: str):
        results = {r.rule_id: r for r in run.device_results[0].rule_results}
        return results[rule_id]

    def test_override_converts_fail_to_not_applicable_with_comment(self) -> None:
        self.service.create_override("dev1", "failing-rule", "doesn't apply to this role")

        run = self.service.run()
        result = self._result_for(run, "failing-rule")

        self.assertEqual(result.status, RuleStatus.NOT_APPLICABLE)
        self.assertEqual(result.override_comment, "doesn't apply to this role")

    def test_override_does_not_affect_a_passing_result(self) -> None:
        self.service.create_override("dev1", "passing-rule", "irrelevant override")

        run = self.service.run()
        result = self._result_for(run, "passing-rule")

        self.assertEqual(result.status, RuleStatus.PASS)
        self.assertIsNone(result.override_comment)

    def test_clearing_override_restores_real_fail_on_next_run(self) -> None:
        self.service.create_override("dev1", "failing-rule", "temporary waiver")
        self.assertEqual(
            self._result_for(self.service.run(), "failing-rule").status, RuleStatus.NOT_APPLICABLE
        )

        self.service.clear_override("dev1", "failing-rule")
        self.assertEqual(
            self._result_for(self.service.run(), "failing-rule").status, RuleStatus.FAIL
        )


if __name__ == "__main__":
    unittest.main()
