"""Cisco IOS / IOSv routers."""

from typing import Any, Dict, List, Optional

from core.models import InterfaceStatus, OspfNeighbor
from devices.base import NetworkDevice
from devices.factory import DeviceFactory


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

    # TODO (collectors): implement the parsers below and test them with the
    # sample outputs saved in tests/samples/cisco_ios/.
    def parse_version(self, output: str) -> Dict[str, Any]:
        raise NotImplementedError("CiscoIOSDevice.parse_version")

    def parse_interfaces(self, output: str) -> List[InterfaceStatus]:
        raise NotImplementedError("CiscoIOSDevice.parse_interfaces")

    def parse_ospf_neighbors(self, output: str) -> List[OspfNeighbor]:
        raise NotImplementedError("CiscoIOSDevice.parse_ospf_neighbors")

    def parse_arp(self, output: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("CiscoIOSDevice.parse_arp")

    def parse_cpu(self, output: str) -> Optional[float]:
        raise NotImplementedError("CiscoIOSDevice.parse_cpu")

    def _apply_config(self, lines: List[str]) -> str:
        output = self._connection.send_config_set(lines)
        output += self._connection.save_config()
        return output
