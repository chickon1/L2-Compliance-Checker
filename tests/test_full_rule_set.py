import re
import unittest

from compliance_checker.models import Platform
from compliance_checker.rule_loader import load_rules

# A config that mentions every gated protocol/feature so we can confirm
# each applies_if pattern actually fires (rather than silently never
# matching due to a typo'd regex).
MULTI_PROTOCOL_CONFIG = """\
hostname multi-protocol-router
!
router bgp 65000
   neighbor 10.0.0.1 password secret
   neighbor 10.0.0.1 prefix-list IN in
   neighbor 10.0.0.1 prefix-list OUT out
!
router ospf 1
   ip ospf authentication message-digest
!
router msdp
   peer 10.0.0.2
      sa-filter in FILTER
      sa-filter out FILTER
      sa-limit 500
   originator-id local-interface Loopback0
!
mpls rsvp
mpls ldp
   router-id interface Loopback0
   mpls ldp sync default
mpls ip
   no mpls icmp ttl-exceeded tunneling
!
vrf instance PROD
interface Ethernet1
   vrf PROD
   route-target import vpn-ipv4 65000:1
   rd 65000:1
   pim ipv4 sparse-mode
   pim ipv4 neighbor-filter NEIGHBORS
   multicast ipv4 boundary BOUND out
   rp address 10.0.0.3 access-list GROUPS
   spt threshold infinity
   ip igmp access-group IGMP_FILTER
   ipv6 address 2001:db8::1/64
   ipv6 nd ra hop-limit 32
   ipv6 nd ra disabled all
!
ip access-list test1
   10 deny ip any any log
!
end
"""


class ProtocolGatedRulesFireTests(unittest.TestCase):
    def test_every_applies_if_gated_rule_matches_the_multi_protocol_config(self) -> None:
        rules = load_rules("src/compliance_checker/rules")
        gated_rules = [r for r in rules if Platform.ARISTA_EOS in r.platforms and r.applies_if]
        self.assertGreater(len(gated_rules), 0, "expected at least one gated Arista rule")

        unmatched = [
            rule.id
            for rule in gated_rules
            if not any(re.search(p, MULTI_PROTOCOL_CONFIG) for p in rule.applies_if)
        ]
        self.assertEqual(unmatched, [], f"applies_if never matched for: {unmatched}")


if __name__ == "__main__":
    unittest.main()
