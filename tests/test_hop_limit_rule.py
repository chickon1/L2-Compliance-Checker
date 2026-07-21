import unittest

from compliance_checker.rule_engine import evaluate
from compliance_checker.rule_loader import load_rules

CONFIG_TEMPLATE = """\
interface Ethernet1
   ipv6 address 2001:db8::1/64
   ipv6 nd ra hop-limit {value}
!
"""


class HopLimitBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        rules = load_rules("src/compliance_checker/rules")
        self.rule = next(r for r in rules if r.id == "stig-v-256057-ipv6-ra-hop-limit")

    def test_passes_at_and_above_threshold(self) -> None:
        for value in (32, 33, 64, 99, 100, 199, 200, 255):
            with self.subTest(value=value):
                result = evaluate(self.rule, CONFIG_TEMPLATE.format(value=value))
                self.assertEqual(result.status, "pass")

    def test_fails_below_threshold(self) -> None:
        for value in (0, 1, 10, 31):
            with self.subTest(value=value):
                result = evaluate(self.rule, CONFIG_TEMPLATE.format(value=value))
                self.assertEqual(result.status, "fail")


if __name__ == "__main__":
    unittest.main()
