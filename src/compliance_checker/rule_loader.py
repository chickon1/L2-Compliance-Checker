"""Loads rule packs from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

from .models import Rule

# Maps a known applies_if regex to a human-readable label, so the UI can
# show "BGP is configured" instead of a raw pattern. Rules using a pattern
# not listed here just fall back to showing the pattern itself.
_APPLIES_IF_LABELS = {
    r"(?im)^router bgp \d+": "BGP is configured",
    r"(?im)^router ospf \d+": "OSPF is configured",
    r"(?im)^router msdp": "MSDP is configured",
    r"(?im)^\s*pim ipv4 sparse-mode": "PIM sparse-mode is enabled on an interface",
    r"(?im)^mpls rsvp": "MPLS RSVP-TE is configured",
    r"(?im)^mpls ldp": "MPLS LDP is configured",
    r"(?im)^mpls ip": "MPLS forwarding is enabled",
    r"(?im)^vrf instance \S+": "A VRF instance is configured",
    r"(?im)^\s*ipv6 address \S+": "IPv6 addressing is configured on an interface",
    r"(?im)^ip access-list \S+": "An IP access-list is configured",
    r"(?im)^mpls ip$": "MPLS forwarding is enabled",
    r"(?im)^vrf definition \S+": "A VRF instance is configured",
    r"(?im)^vrf context \S+": "A VRF instance is configured",
    r"(?im)^\s*ip pim sparse-mode": "PIM sparse-mode is enabled on an interface",
    r"(?im)^ip msdp peer": "MSDP is configured",
    r"(?im)^feature msdp": "MSDP is configured",
    r"(?im)^feature mpls": "MPLS is enabled",
    r"(?im)^feature lldp$": "LLDP is enabled",
    r"(?im)^feature vtp$": "VTP is enabled",
    r"(?im)^snmp-server": "SNMP is configured",
    r"(?im)^set snmp": "SNMP is configured",
    r"(?im)^set system ntp server": "NTP is configured",
    r"(?im)^set security certificates|^set system services web-management https": "A PKI/HTTPS certificate is configured",
    r"(?im)^set protocols (rstp|mstp)": "RSTP/MSTP is configured",
    r"(?im)^set interfaces \S+ unit \d+ family ethernet-switching interface-mode trunk": "A trunk port is configured",
    r"(?im)^set protocols bgp group \S+": "BGP is configured",
    r"(?im)^set protocols (bgp group \S+|ospf area \S+ interface \S+)": "BGP or OSPF is configured",
    r"(?im)^set protocols ldp": "MPLS LDP is configured",
    r"(?im)^set protocols msdp": "MSDP is configured",
    r"(?im)^set protocols pim interface": "PIM is configured",
    r"(?im)^set firewall family inet filter": "A firewall filter is configured",
    r"(?im)^set protocols mpls": "MPLS forwarding is enabled",
    r"(?im)^set interfaces \S+ (unit \d+ )?family inet6 address": "IPv6 addressing is configured on an interface",
}


def _label_for(applies_if: List[str]) -> str:
    labels = [_APPLIES_IF_LABELS.get(pattern, pattern) for pattern in applies_if]
    return " or ".join(dict.fromkeys(labels))


def load_rules(rules_dir: str) -> List[Rule]:
    rules: List[Rule] = []
    for path in sorted(Path(rules_dir).glob("*.yaml")):
        entries = yaml.safe_load(path.read_text()) or []
        for entry in entries:
            rule = Rule.model_validate(entry)
            if rule.applies_if:
                rule = rule.model_copy(update={"applies_if_label": _label_for(rule.applies_if)})
            rules.append(rule)
    return rules
