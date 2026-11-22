"""Cisco IOS / IOSv routers.

Not part of the current GNS3 lab (which uses MikroTik + VyOS); kept as a third
vendor to show that new platforms plug in without changing other classes.
Parsing uses the community TextFSM templates (``ntc-templates``).
"""

import re
from typing import Any, Dict, List, Optional

from core.models import InterfaceStatus, OspfNeighbor
from devices.base import NetworkDevice
from devices.factory import DeviceFactory
from devices.parsing import duration_to_seconds


def _textfsm(command: str, output: str) -> List[Dict[str, str]]:
    from ntc_templates.parse import parse_output

    return parse_output(platform="cisco_ios", command=command, data=output)


@DeviceFactory.register("cisco_ios")
class CiscoIOSDevice(NetworkDevice):
    """Cisco IOS platform."""

    @property
    def vendor(self) -> str:
        return "Cisco IOS"

    @property
    def netmiko_device_type(self) -> str:
        return "cisco_ios"

    @property
    def commands(self) -> Dict[str, str]:
        return {
            "version": "show version",
            "interfaces": "show ip interface brief",
            "ospf_neighbors": "show ip ospf neighbor",
            "arp": "show ip arp",
            "cpu": "show processes cpu | include CPU utilization",
            "running_config": "show running-config",
        }

    def parse_version(self, output: str) -> Dict[str, Any]:
        rows = _textfsm("show version", output)
        row = rows[0] if rows else {}
        serial = row.get("serial") or None
        if isinstance(serial, list):
            serial = serial[0] if serial else None
        return {
            "hostname": row.get("hostname") or None,
            "os_version": f"IOS {row['version']}" if row.get("version") else None,
            "serial": serial,
            "uptime_seconds": duration_to_seconds(row.get("uptime", "")),
        }

    def parse_interfaces(self, output: str) -> List[InterfaceStatus]:
        result = []
        for row in _textfsm("show ip interface brief", output):
            ip = row.get("ip_address")
            result.append(
                InterfaceStatus(
                    name=row["interface"],
                    ip_address=None if ip in (None, "", "unassigned") else ip,
                    admin_up=row.get("status") != "administratively down",
                    oper_up=row.get("proto") == "up",
                )
            )
        return result

    def parse_ospf_neighbors(self, output: str) -> List[OspfNeighbor]:
        return [
            OspfNeighbor(
                neighbor_id=row["neighbor_id"],
                address=row.get("ip_address", ""),
                interface=row.get("interface", ""),
                state=row.get("state", "").split("/")[0],
            )
            for row in _textfsm("show ip ospf neighbor", output)
        ]

    def parse_arp(self, output: str) -> List[Dict[str, Any]]:
        result = []
        for row in _textfsm("show ip arp", output):
            mac = row.get("mac_address", "")
            if not re.fullmatch(r"[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}", mac, re.IGNORECASE):
                continue
            plain = mac.replace(".", "").lower()
            result.append(
                {
                    "ip": row["ip_address"],
                    "mac": ":".join(plain[i:i + 2] for i in range(0, 12, 2)),
                    "interface": row.get("interface", ""),
                }
            )
        return result

    def parse_cpu(self, output: str) -> Optional[float]:
        match = re.search(r"five minutes:\s*(\d+)%", output)
        return float(match.group(1)) if match else None

    def _apply_config(self, lines: List[str]) -> str:
        output = self._connection.send_config_set(lines)
        if re.search(r"% Invalid input|% Incomplete command", output):
            raise RuntimeError(output.strip()[-500:])
        output += self._connection.save_config()
        return output
