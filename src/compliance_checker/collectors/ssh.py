"""Pulls running-config from a device over SSH via Netmiko."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import NamedTuple, Optional, Protocol

from netmiko import ConnectHandler

from ..credentials import Credentials
from ..models import Device, Platform

_SHOW_CONFIG_COMMAND = {
    Platform.JUNIPER_JUNOS: "show configuration | display set",
}


class CollectedConfig(NamedTuple):
    device_id: str
    collected_at: datetime
    raw_config: str


class ConfigCollector(Protocol):
    def collect(self, device: Device, credentials: Optional[Credentials]) -> CollectedConfig: ...


class SshConfigCollector:
    def collect(self, device: Device, credentials: Optional[Credentials]) -> CollectedConfig:
        if credentials is None:
            raise ValueError(f"device {device.id!r} has no credential profile assigned")
        connection = ConnectHandler(
            device_type=device.platform.value,
            host=device.management_address,
            port=device.ssh_port,
            username=credentials.username,
            password=credentials.password,
        )
        command = _SHOW_CONFIG_COMMAND.get(device.platform, "show running-config")
        try:
            raw_config = connection.send_command(command)
        finally:
            connection.disconnect()
        return CollectedConfig(
            device_id=device.id,
            collected_at=datetime.now(timezone.utc),
            raw_config=raw_config,
        )
