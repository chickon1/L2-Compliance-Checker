import unittest

from compliance_checker.models import Rule, RuleStatus, Severity
from compliance_checker.rule_engine import _humanize_pattern, evaluate, evaluate_all


class HumanizePatternTests(unittest.TestCase):
    def test_strips_flags_anchors_and_escapes(self) -> None:
        self.assertEqual(_humanize_pattern(r"(?im)^banner login"), "banner login")

    def test_replaces_placeholders(self) -> None:
        self.assertEqual(
            _humanize_pattern(r"(?im)^\s*neighbor \S+ maximum-routes \d+"),
            "neighbor <value> maximum-routes <number>",
        )

    def test_falls_back_for_complex_patterns(self) -> None:
        result = _humanize_pattern(r"(?im)^\s*(no lldp run|no lldp transmit|no lldp receive)")
        self.assertEqual(result, "the required configuration")
        self.assertNotIn("(", result)

PASSING_CONFIG = """\
hostname lab-sw1
!
no ip http server
aaa authentication login default group tacacs+ local
line vty 0 4
 exec-timeout 10 0
service password-encryption
banner motd ^ Authorized access only ^
ntp server 192.168.100.1
end
"""

FAILING_CONFIG = """\
hostname lab-sw1
!
ip http server
line vty 0 4
 transport input telnet
snmp-server community public RO
end
"""


class RequireRuleTests(unittest.TestCase):
    def test_passes_when_pattern_present(self) -> None:
        rule = Rule(
            id="aaa-login-configured",
            description="AAA login required",
            severity=Severity.HIGH,
            require=[r"(?im)^aaa authentication login"],
        )
        result = evaluate(rule, PASSING_CONFIG)
        self.assertEqual(result.status, RuleStatus.PASS)
        self.assertTrue(result.evidence)

    def test_fails_when_pattern_absent(self) -> None:
        rule = Rule(
            id="aaa-login-configured",
            description="AAA login required",
            severity=Severity.HIGH,
            require=[r"(?im)^aaa authentication login"],
        )
        result = evaluate(rule, FAILING_CONFIG)
        self.assertEqual(result.status, RuleStatus.FAIL)
        self.assertTrue(result.evidence, "a failed require check should explain what was expected")
        # Human-readable, not raw regex syntax like "(?im)" or "\\s*".
        self.assertNotIn("(?", result.evidence[0])
        self.assertIn("aaa authentication login", result.evidence[0])


class ForbidRuleTests(unittest.TestCase):
    def test_passes_when_pattern_absent(self) -> None:
        rule = Rule(
            id="no-telnet-server",
            description="No telnet transport",
            severity=Severity.HIGH,
            forbid=[r"(?im)^\s*transport input\s+.*\btelnet\b"],
        )
        result = evaluate(rule, PASSING_CONFIG)
        self.assertEqual(result.status, RuleStatus.PASS)

    def test_fails_when_pattern_present(self) -> None:
        rule = Rule(
            id="no-telnet-server",
            description="No telnet transport",
            severity=Severity.HIGH,
            forbid=[r"(?im)^\s*transport input\s+.*\btelnet\b"],
        )
        result = evaluate(rule, FAILING_CONFIG)
        self.assertEqual(result.status, RuleStatus.FAIL)
        self.assertTrue(result.evidence)


class EvaluateAllTests(unittest.TestCase):
    def test_evaluates_every_rule(self) -> None:
        rules = [
            Rule(
                id="no-http-server",
                description="HTTP server disabled",
                severity=Severity.HIGH,
                require=[r"(?im)^no ip http server"],
            ),
            Rule(
                id="no-default-snmp-community",
                description="No default SNMP community",
                severity=Severity.HIGH,
                forbid=[r"(?im)^snmp-server community\s+(public|private)\b"],
            ),
        ]
        results = evaluate_all(rules, FAILING_CONFIG)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.status == RuleStatus.FAIL for r in results))


if __name__ == "__main__":
    unittest.main()
