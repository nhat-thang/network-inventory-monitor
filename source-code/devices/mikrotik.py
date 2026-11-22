"""MikroTik RouterOS routers (tested on CHR 7.24.6)."""

import re
from typing import Any, Dict, List, Optional

from core.models import InterfaceStatus, OspfNeighbor
from devices.base import NetworkDevice
from devices.factory import DeviceFactory
from devices.parsing import duration_to_seconds, key_value_block, terse_line


@DeviceFactory.register("mikrotik_routeros")
class MikroTikDevice(NetworkDevice):
    """MikroTik RouterOS platform.

    RouterOS answers "version" and "interfaces" with several commands, so this
    class overrides the ``collect_version`` and ``collect_interfaces`` hooks.
    """

    @property
    def vendor(self) -> str:
        return "MikroTik RouterOS"

    @property
    def netmiko_device_type(self) -> str:
        return "mikrotik_routeros"

    @property
    def commands(self) -> Dict[str, str]:
        return {
            "version": "/system resource print",
            "identity": "/system identity print",
            "license": "/system license print",
            "interfaces": "/interface print terse without-paging",
            "ip_addresses": "/ip address print terse without-paging",
            "ospf_neighbors": "/routing ospf neighbor print terse without-paging",
            "arp": "/ip arp print terse without-paging",
            "cpu": "/system resource print",
            "running_config": "/export",
        }

    # ----------------------------------------------------------------- hooks
    def collect_version(self) -> Dict[str, Any]:
        cmd = self.commands
        info = self.parse_version(self.send_command(cmd["version"]))
        info["hostname"] = key_value_block(self.send_command(cmd["identity"])).get("name")
        license_info = key_value_block(self.send_command(cmd["license"]))
        info["serial"] = license_info.get("system-id") or license_info.get("software-id")
        return info

    def collect_interfaces(self) -> List[InterfaceStatus]:
        interfaces = self.parse_interfaces(self.send_command(self.commands["interfaces"]))
        addresses = self.parse_ip_addresses(self.send_command(self.commands["ip_addresses"]))
        for intf in interfaces:
            intf.ip_address = addresses.get(intf.name)
        return interfaces

    # --------------------------------------------------------------- parsers
    def parse_version(self, output: str) -> Dict[str, Any]:
        """Parse ``/system resource print`` (version and uptime)."""
        data = key_value_block(output)
        return {
            "hostname": None,
            "os_version": f"RouterOS {data['version']}" if data.get("version") else None,
            "serial": None,
            "uptime_seconds": duration_to_seconds(data.get("uptime", "")),
        }

    def parse_interfaces(self, output: str) -> List[InterfaceStatus]:
        """Parse ``/interface print terse``; flag R = running, X = disabled."""
        result = []
        for line in output.splitlines():
            flags, fields = terse_line(line)
            if "name" not in fields:
                continue
            result.append(
                InterfaceStatus(
                    name=fields["name"],
                    ip_address=None,
                    admin_up="X" not in flags and fields.get("disabled") != "yes",
                    oper_up="R" in flags or fields.get("running") == "yes",
                )
            )
        return result

    @staticmethod
    def parse_ip_addresses(output: str) -> Dict[str, str]:
        """Parse ``/ip address print terse`` into {interface: "ip/prefix"} (first address wins)."""
        result: Dict[str, str] = {}
        for line in output.splitlines():
            flags, fields = terse_line(line)
            if "X" in flags or "address" not in fields or "interface" not in fields:
                continue
            result.setdefault(fields["interface"], fields["address"])
        return result

    def parse_ospf_neighbors(self, output: str) -> List[OspfNeighbor]:
        """Parse ``/routing ospf neighbor print terse`` (RouterOS 7)."""
        result = []
        for line in output.splitlines():
            _, fields = terse_line(line)
            if "router-id" not in fields:
                continue
            result.append(
                OspfNeighbor(
                    neighbor_id=fields["router-id"],
                    address=fields.get("address", ""),
                    interface=fields.get("interface", fields.get("area", "")),
                    state=fields.get("state", ""),
                )
            )
        return result

    def parse_arp(self, output: str) -> List[Dict[str, Any]]:
        """Parse ``/ip arp print terse``; entries without a MAC are skipped."""
        result = []
        for line in output.splitlines():
            _, fields = terse_line(line)
            if not fields.get("address") or not fields.get("mac-address"):
                continue
            result.append(
                {
                    "ip": fields["address"],
                    "mac": fields["mac-address"].lower(),
                    "interface": fields.get("interface", ""),
                }
            )
        return result

    def parse_cpu(self, output: str) -> Optional[float]:
        """Read ``cpu-load: 3%`` from ``/system resource print``."""
        match = re.search(r"cpu-load:\s*(\d+(?:\.\d+)?)\s*%", output)
        return float(match.group(1)) if match else None

    # ---------------------------------------------------------------- config
    def backup_config(self) -> str:
        """``/export`` without the timestamp header, so unchanged configs compare equal."""
        text = self.send_command(self.commands["running_config"])
        return "\n".join(line for line in text.splitlines() if not line.startswith("# 20"))

    def _apply_config(self, lines: List[str]) -> str:
        # RouterOS applies every command immediately and saves it automatically.
        output = []
        for line in lines:
            reply = self._connection.send_command(line, expect_string=r"\] >")
            if re.search(r"failure:|syntax error|bad command|expected ", reply):
                raise RuntimeError(f"{line!r}: {reply.strip()}")
            output.append(f"{line}\n{reply}")
        return "\n".join(output)
