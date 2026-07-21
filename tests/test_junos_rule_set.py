import re
import unittest

from compliance_checker.models import Platform
from compliance_checker.rule_loader import load_rules

JUNOS_MULTI_PROTOCOL_CONFIG = """\
set system host-name junos-multi-protocol
set system login message "authorized use only"
set system login retry-options tries-before-disconnect 3
set system login retry-options lockout-period 15
set system login idle-timeout 5
set system login password minimum-length 15
set system login password format sha512
set system services ssh protocol-version v2
set system services ssh ciphers aes256-ctr
set system ntp server 192.168.100.1 key 1
set system ntp authentication-key 1 type sha256 value secret
set snmp v3 usm local-engine user snmpadmin authentication-sha authentication-password secret
set security certificates local ca-profile DOD-PKI
set protocols rstp bpdu-block-on-edge
set protocols rstp interface ge-0/0/1 no-root-port
set protocols rstp interface ge-0/0/1 loop-protect
set interfaces ge-0/0/2 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/2 native-vlan-id 999
set protocols bgp group EXTERNAL type external
set protocols bgp group EXTERNAL import BGP-IN
set protocols bgp group EXTERNAL export BGP-OUT
set protocols bgp group EXTERNAL ttl 1
set protocols bgp group EXTERNAL authentication-algorithm hmac-sha-1-96
set protocols bgp group EXTERNAL family inet unicast prefix-limit maximum 500000
set protocols ospf area 0.0.0.0 interface ge-0/0/1.0
set protocols ospf area 0.0.0.0 interface ge-0/0/1.0 authentication
set protocols ospf area 0.0.0.0 interface ge-0/0/1.0 ldp-synchronization
set protocols ldp interface ge-0/0/1.0
set protocols ldp session 192.168.100.2 authentication-key secret
set protocols msdp group PEERS peer 192.168.100.3 authentication-key secret
set protocols msdp group PEERS peer 192.168.100.3 import MSDP-SA-IN
set protocols pim interface ge-0/0/1.0 neighbor-policy PIM-NEIGHBORS
set protocols pim interface ge-0/0/1.0 multicast-scoping
set protocols mpls no-propagate-ttl
set firewall family inet filter PROTECT-RE term allow-mgmt then accept
set firewall family inet filter PROTECT-RE term deny-rest then discard
set firewall family inet filter PROTECT-RE term deny-rest then log
set firewall family inet filter PROTECT-RE term no-ip-options from ip-options any
set interfaces ge-0/0/0 unit 0 family inet filter input PROTECT-RE
set interfaces ge-0/0/0 unit 0 family inet rpf-check mode loose
set interfaces ge-0/0/0 unit 0 family inet no-gratuitous-arp-request
set interfaces ge-0/0/0 unit 0 family inet no-redirects
set interfaces ge-0/0/1 unit 0 family inet6 address 2001:db8::1/64
set protocols router-advertisement interface ge-0/0/1.0 current-hop-limit 64
set protocols router-advertisement interface ge-0/0/0.0 no-advertise
set firewall family inet6 filter IPV6-IN term block-routing-hdr from next-header routing
set interfaces ge-0/0/0 unit 0 family inet6 filter input IPV6-IN
set system tacplus-server 192.168.100.20 secret secret
set system authentication-order [ tacplus password ]
set system syslog host 192.168.100.10 any notice
set system syslog file messages any notice
"""


class JunosAppliesIfGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_rules("src/compliance_checker/rules")

    def test_every_gated_junos_rule_matches_the_multi_protocol_config(self) -> None:
        gated = [r for r in self.rules if Platform.JUNIPER_JUNOS in r.platforms and r.applies_if]
        self.assertGreater(len(gated), 0, "expected at least one gated Junos rule")
        unmatched = [
            rule.id
            for rule in gated
            if not any(re.search(p, JUNOS_MULTI_PROTOCOL_CONFIG) for p in rule.applies_if)
        ]
        self.assertEqual(unmatched, [], f"applies_if never matched for: {unmatched}")


class JunosRuleSetSanityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = [
            r for r in load_rules("src/compliance_checker/rules") if Platform.JUNIPER_JUNOS in r.platforms
        ]

    def test_at_least_one_rule_loaded_per_pack(self) -> None:
        self.assertGreater(len(self.rules), 40)

    def test_every_rule_has_require_or_forbid(self) -> None:
        empty = [r.id for r in self.rules if not r.require and not r.forbid]
        self.assertEqual(empty, [])

    def test_every_rule_scoped_only_to_juniper_junos(self) -> None:
        wrong_scope = [r.id for r in self.rules if r.platforms != [Platform.JUNIPER_JUNOS]]
        self.assertEqual(wrong_scope, [])


class Ipv6HopLimitThresholdTests(unittest.TestCase):
    """Mirrors the Cisco/Arista fix: hop-limit >= 32 must be a real numeric
    threshold check, not just presence."""

    def setUp(self) -> None:
        rules = load_rules("src/compliance_checker/rules")
        self.rule = next(r for r in rules if r.id == "junos-stig-v254071-ipv6-ra-hop-limit")

    def _matches(self, value: int) -> bool:
        config = f"set protocols router-advertisement interface ge-0/0/1.0 current-hop-limit {value}\n"
        return any(re.search(p, config) for p in self.rule.require)

    def test_below_threshold_fails(self) -> None:
        self.assertFalse(self._matches(31))

    def test_at_and_above_threshold_passes(self) -> None:
        self.assertTrue(self._matches(32))
        self.assertTrue(self._matches(64))
        self.assertTrue(self._matches(255))


if __name__ == "__main__":
    unittest.main()
