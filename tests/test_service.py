import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from compliance_checker.collectors.ssh import CollectedConfig
from compliance_checker.models import Device, Platform, Rule, Severity
from compliance_checker.repository import Repository
from compliance_checker.service import ComplianceService


class StubCollector:
    def collect(self, device, credentials):
        return CollectedConfig(
            device_id=device.id, collected_at=datetime.now(timezone.utc), raw_config=""
        )


class ConfigByDeviceCollector:
    def __init__(self, config_by_device_id):
        self._config_by_device_id = config_by_device_id

    def collect(self, device, credentials):
        return CollectedConfig(
            device_id=device.id,
            collected_at=datetime.now(timezone.utc),
            raw_config=self._config_by_device_id[device.id],
        )


class OneDeviceFailsCollector:
    """Raises for a specific device_id, succeeds for everything else."""

    def __init__(self, failing_device_id: str):
        self._failing_device_id = failing_device_id

    def collect(self, device, credentials):
        if device.id == self._failing_device_id:
            raise ConnectionError("Authentication to device failed.")
        return CollectedConfig(
            device_id=device.id, collected_at=datetime.now(timezone.utc), raw_config="hostname x"
        )


class PlatformScopedRuleFilteringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self._tmpdir.name) / "test.db")
        self.repository = Repository(db_path)

        self.ios_device = Device(
            id="ios1", name="ios1", management_address="10.0.0.1", platform=Platform.CISCO_IOS
        )
        self.eos_device = Device(
            id="eos1", name="eos1", management_address="10.0.0.2", platform=Platform.ARISTA_EOS
        )
        self.repository.add_devices([self.ios_device, self.eos_device])

        self.rules = [
            Rule(
                id="ios-only",
                description="Cisco-only rule",
                severity=Severity.HIGH,
                platforms=[Platform.CISCO_IOS],
                require=["nonexistent-pattern"],
            ),
            Rule(
                id="eos-only",
                description="Arista-only rule",
                severity=Severity.HIGH,
                platforms=[Platform.ARISTA_EOS],
                require=["nonexistent-pattern"],
            ),
            Rule(
                id="all-platforms",
                description="Applies everywhere",
                severity=Severity.LOW,
                require=["nonexistent-pattern"],
            ),
        ]
        self.service = ComplianceService(StubCollector(), self.rules, self.repository)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_each_device_only_evaluated_against_applicable_rules(self) -> None:
        run = self.service.run()
        results_by_device = {r.device_id: r for r in run.device_results}

        ios_rule_ids = {r.rule_id for r in results_by_device["ios1"].rule_results}
        eos_rule_ids = {r.rule_id for r in results_by_device["eos1"].rule_results}

        self.assertEqual(ios_rule_ids, {"ios-only", "all-platforms"})
        self.assertEqual(eos_rule_ids, {"eos-only", "all-platforms"})


class AppliesIfProtocolGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self._tmpdir.name) / "test.db")
        self.repository = Repository(db_path)

        self.bgp_device = Device(
            id="bgp1", name="bgp1", management_address="10.0.0.1", platform=Platform.ARISTA_EOS
        )
        self.no_bgp_device = Device(
            id="nobgp1",
            name="nobgp1",
            management_address="10.0.0.2",
            platform=Platform.ARISTA_EOS,
        )
        self.repository.add_devices([self.bgp_device, self.no_bgp_device])

        self.rules = [
            Rule(
                id="bgp-neighbor-auth",
                description="BGP neighbors must be authenticated",
                severity=Severity.HIGH,
                applies_if=[r"(?im)^router bgp \d+"],
                require=[r"(?im)^\s*neighbor \S+ password"],
            ),
        ]
        collector = ConfigByDeviceCollector(
            {
                "bgp1": "router bgp 65000\n neighbor 10.0.0.9 password secret\n",
                "nobgp1": "hostname nobgp1\n",
            }
        )
        self.service = ComplianceService(collector, self.rules, self.repository)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_rule_only_evaluated_when_config_matches_applies_if(self) -> None:
        run = self.service.run()
        results_by_device = {r.device_id: r for r in run.device_results}

        self.assertEqual(
            {r.rule_id for r in results_by_device["bgp1"].rule_results}, {"bgp-neighbor-auth"}
        )
        self.assertEqual(results_by_device["nobgp1"].rule_results, [])


class OneDeviceCollectionFailureTests(unittest.TestCase):
    """Regression test: a single device with bad credentials/unreachable must
    not abort the whole batch run and wipe out every other device's results."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))

        self.good_device = Device(
            id="good1", name="good1", management_address="10.0.0.1", platform=Platform.ARISTA_EOS
        )
        self.bad_device = Device(
            id="bad1", name="bad1", management_address="10.0.0.2", platform=Platform.ARISTA_EOS
        )
        self.repository.add_devices([self.good_device, self.bad_device])

        self.rules = [
            Rule(
                id="hostname-present",
                description="hostname must be set",
                severity=Severity.LOW,
                require=["hostname"],
            )
        ]
        collector = OneDeviceFailsCollector(failing_device_id="bad1")
        self.service = ComplianceService(collector, self.rules, self.repository)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_good_device_still_gets_results_when_another_device_fails(self) -> None:
        run = self.service.run()
        results_by_device = {r.device_id: r for r in run.device_results}

        self.assertEqual(len(run.device_results), 2, "both devices should appear in the run")

        good_result = results_by_device["good1"]
        self.assertIsNone(good_result.collection_error)
        self.assertEqual(len(good_result.rule_results), 1)
        self.assertEqual(good_result.rule_results[0].status, "pass")

        bad_result = results_by_device["bad1"]
        self.assertIsNotNone(bad_result.collection_error)
        self.assertIn("Authentication", bad_result.collection_error)
        self.assertEqual(bad_result.rule_results, [])

    def test_run_is_persisted_and_finished_despite_the_failure(self) -> None:
        self.service.run()
        stored = self.repository.latest_run()

        self.assertIsNotNone(stored)
        self.assertIsNotNone(stored.finished_at)
        self.assertEqual(len(stored.device_results), 2)


if __name__ == "__main__":
    unittest.main()
