import unittest
from pathlib import Path

import yaml

from compliance_checker.collectors.mock import _SAMPLE_CONFIG
from compliance_checker.models import Rule
from compliance_checker.rule_engine import evaluate_all


class BaselineRulesTests(unittest.TestCase):
    def test_mock_sample_config_passes_all_baseline_rules(self) -> None:
        # Scoped to baseline.yaml specifically (the small generic-hygiene
        # pack), not the full comprehensive Cisco STIG rule packs — the mock
        # sample config is a hand-written demo config, not a STIG-hardened
        # device, so it's only expected to satisfy the basic pack.
        entries = yaml.safe_load(Path("src/compliance_checker/rules/baseline.yaml").read_text())
        rules = [Rule.model_validate(entry) for entry in entries]
        config = _SAMPLE_CONFIG.format(name="lab-sw1")
        results = evaluate_all(rules, config)
        failed = [r.rule_id for r in results if r.status != "pass"]
        self.assertEqual(failed, [], f"unexpected failures: {failed}")


if __name__ == "__main__":
    unittest.main()
