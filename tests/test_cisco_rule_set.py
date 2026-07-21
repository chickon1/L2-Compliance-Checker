import re
import unittest

from compliance_checker.models import Platform
from compliance_checker.rule_loader import load_rules

IOS_MULTI_PROTOCOL_CONFIG = """\
hostname ios-multi-protocol
!
router bgp 65000
 neighbor 10.0.0.1 password secret
 neighbor 10.0.0.1 maximum-prefix 1000
 neighbor 10.0.0.1 update-source Loopback0
 neighbor 10.0.0.1 ttl-security hops 1
!
vtp domain LAB
vtp mode transparent
!
mpls ip
mpls ldp
 router-id Loopback0
 neighbor 10.0.0.2 password secret
 igp sync
!
vrf definition PROD
 rd 65000:1
!
snmp-server group STIG_GROUP v3 priv
snmp-server user snmpadmin STIG_GROUP v3 auth sha authpass priv aes 128 privpass
!
interface Loopback0
 ip pim sparse-mode
 ip pim neighbor-filter NEIGHBORS
 ipv6 address 2001:db8::1/64
!
ip msdp peer 10.0.0.3 password secret
!
end
"""

NXOS_MULTI_PROTOCOL_CONFIG = """\
hostname nxos-multi-protocol
!
feature bgp
router bgp 65000
  neighbor 10.0.0.1
    password secret
    maximum-prefix 1000
    update-source loopback0
!
feature vtp
vtp password secret
!
feature lldp
!
feature mpls
no mpls ip propagate-ttl
mpls ldp neighbor 10.0.0.2 password secret
mpls ldp router-id loopback0
mpls ldp sync
!
vrf context PROD
  rd 65000:1
!
feature msdp
ip msdp password 10.0.0.3 secret
!
snmp-server user snmpadmin network-admin auth sha authpass priv aes-128 privpass
!
interface loopback0
  ip pim sparse-mode
  ipv6 address 2001:db8::1/64
!
end
"""


class CiscoAppliesIfGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_rules("src/compliance_checker/rules")

    def _gated_rules_for(self, platform: Platform):
        return [r for r in self.rules if platform in r.platforms and r.applies_if]

    def test_every_gated_ios_rule_matches_the_multi_protocol_config(self) -> None:
        gated = self._gated_rules_for(Platform.CISCO_IOS)
        self.assertGreater(len(gated), 0, "expected at least one gated Cisco IOS rule")
        unmatched = [
            rule.id
            for rule in gated
            if not any(re.search(p, IOS_MULTI_PROTOCOL_CONFIG) for p in rule.applies_if)
        ]
        self.assertEqual(unmatched, [], f"applies_if never matched for: {unmatched}")

    def test_every_gated_nxos_rule_matches_the_multi_protocol_config(self) -> None:
        gated = self._gated_rules_for(Platform.CISCO_NXOS)
        self.assertGreater(len(gated), 0, "expected at least one gated Cisco NX-OS rule")
        unmatched = [
            rule.id
            for rule in gated
            if not any(re.search(p, NXOS_MULTI_PROTOCOL_CONFIG) for p in rule.applies_if)
        ]
        self.assertEqual(unmatched, [], f"applies_if never matched for: {unmatched}")


class RuleSetSanityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_rules("src/compliance_checker/rules")

    def test_no_duplicate_rule_ids(self) -> None:
        ids = [r.id for r in self.rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        self.assertEqual(dupes, set())

    def test_password_encryption_only_scoped_to_ios(self) -> None:
        rule = next(r for r in self.rules if r.id == "password-encryption-enabled")
        self.assertEqual(rule.platforms, [Platform.CISCO_IOS])

    def test_every_rule_has_require_or_forbid(self) -> None:
        empty = [r.id for r in self.rules if not r.require and not r.forbid]
        self.assertEqual(empty, [])


class Ipv6HopLimitThresholdTests(unittest.TestCase):
    """The STIG requires hop-limit >= 32 — this must be a real numeric
    threshold check, not just presence, for both Cisco platforms."""

    def setUp(self) -> None:
        rules = load_rules("src/compliance_checker/rules")
        self.ios_rule = next(r for r in rules if r.id == "stig-v-230039-ipv6-ra-hop-limit")
        self.nxos_rule = next(r for r in rules if r.id == "stig-v-237754-ipv6-ra-hop-limit")

    def _matches(self, rule, value: int) -> bool:
        config = f"ipv6 hop-limit {value}\n"
        return any(re.search(p, config) for p in rule.require)

    def test_ios_below_threshold_fails(self) -> None:
        self.assertFalse(self._matches(self.ios_rule, 31))

    def test_ios_at_and_above_threshold_passes(self) -> None:
        self.assertTrue(self._matches(self.ios_rule, 32))
        self.assertTrue(self._matches(self.ios_rule, 64))
        self.assertTrue(self._matches(self.ios_rule, 255))

    def test_nxos_below_threshold_fails(self) -> None:
        self.assertFalse(self._matches(self.nxos_rule, 31))

    def test_nxos_at_and_above_threshold_passes(self) -> None:
        self.assertTrue(self._matches(self.nxos_rule, 32))
        self.assertTrue(self._matches(self.nxos_rule, 64))


if __name__ == "__main__":
    unittest.main()
