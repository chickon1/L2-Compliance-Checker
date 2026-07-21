"""Serves canned sample configs so the app runs without the GNS3 lab powered on."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..credentials import Credentials
from ..models import Device
from .ssh import CollectedConfig

_SAMPLE_CONFIG = """\
hostname {name}
!
no ip http server
no ip http secure-server
!
aaa new-model
aaa authentication login default group tacacs+ local
!
line vty 0 4
 exec-timeout 10 0
 transport input ssh
!
service password-encryption
!
banner motd ^ Authorized access only. ^
!
ntp server 192.168.100.1
!
end
"""


class MockConfigCollector:
    def collect(self, device: Device, credentials: Optional[Credentials]) -> CollectedConfig:
        return CollectedConfig(
            device_id=device.id,
            collected_at=datetime.now(timezone.utc),
            raw_config=_SAMPLE_CONFIG.format(name=device.name),
        )
