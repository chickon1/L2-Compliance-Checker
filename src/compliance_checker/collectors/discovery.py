"""Scans an address range for open SSH ports and identifies platform/hostname."""

from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import List

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
from netmiko.ssh_autodetect import SSHDetect

from ..credentials import Credentials
from ..models import DiscoveredHost, Platform

_KNOWN_PLATFORMS = {p.value for p in Platform}
_CONNECT_TIMEOUT = 1.5


def _parse_range(range_str: str) -> List[str]:
    range_str = range_str.strip()
    if "/" in range_str:
        network = ipaddress.ip_network(range_str, strict=False)
        return [str(ip) for ip in network.hosts()]
    if "-" in range_str:
        start_str, end_str = (part.strip() for part in range_str.split("-", 1))
        start = ipaddress.ip_address(start_str)
        if "." in end_str or ":" in end_str:
            end = ipaddress.ip_address(end_str)
        else:
            prefix = start_str.rsplit(".", 1)[0]
            end = ipaddress.ip_address(f"{prefix}.{end_str}")
        addresses = []
        current = int(start)
        while current <= int(end):
            addresses.append(str(ipaddress.ip_address(current)))
            current += 1
        return addresses
    return [range_str]


def _port_open(address: str, port: int) -> bool:
    try:
        with socket.create_connection((address, port), timeout=_CONNECT_TIMEOUT):
            return True
    except OSError:
        return False


def scan_range(range_str: str, port: int = 22) -> List[str]:
    """Returns the addresses in range_str with an open TCP port."""
    addresses = _parse_range(range_str)
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda addr: (addr, _port_open(addr, port)), addresses))
    return [addr for addr, open_ in results if open_]


def _clean_hostname(prompt: str) -> str:
    hostname = prompt.strip()
    for suffix in ("(config-if)", "(config-vlan)", "(config)"):
        hostname = hostname.replace(suffix, "")
    return hostname.rstrip("#>").strip()


def detect_platform(address: str, port: int, credentials: Credentials) -> DiscoveredHost:
    """Identifies a reachable host's platform and configured hostname, never raising."""
    connect_params = {
        "host": address,
        "port": port,
        "username": credentials.username,
        "password": credentials.password,
    }
    try:
        best_match = SSHDetect(device_type="autodetect", **connect_params).autodetect()
    except NetmikoAuthenticationException:
        return DiscoveredHost(address=address, reachable=True, auth_ok=False)
    except (NetmikoTimeoutException, OSError):
        return DiscoveredHost(address=address, reachable=False, auth_ok=False)

    if best_match not in _KNOWN_PLATFORMS:
        return DiscoveredHost(address=address, reachable=True, auth_ok=True)

    hostname = None
    try:
        connection = ConnectHandler(device_type=best_match, **connect_params)
        try:
            hostname = _clean_hostname(connection.find_prompt())
        finally:
            connection.disconnect()
    except Exception:
        hostname = None

    return DiscoveredHost(
        address=address,
        reachable=True,
        auth_ok=True,
        guessed_platform=Platform(best_match),
        guessed_hostname=hostname,
    )
