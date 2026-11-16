"""VyOS routers."""

from typing import Any, Dict, List, Optional

from core.models import InterfaceStatus, OspfNeighbor
from devices.base import NetworkDevice
from devices.factory import DeviceFactory


@DeviceFactory.register("vyos")
class VyOSDevice(NetworkDevice):
    """VyOS platform (configuration needs an explicit commit and save)."""

    @property
    def vendor(self) -> str:
        return "VyOS"

    @property
    def netmiko_device_type(self) -> str:
        return "vyos"

    @property
    def commands(self) -> Dict[str, str]:
        # TODO (lab): confirm each command on the VyOS version used in GNS3.
        return {
            "version": "show version",
            "interfaces": "show interfaces",
            "ospf_neighbors": "show ip ospf neighbor",
            "arp": "show arp",
            "cpu": "show system cpu",
            "running_config": "show configuration commands",
        }

    # TODO (collectors): implement the parsers below and test them with the
    # sample outputs saved in tests/samples/vyos/.
    def parse_version(self, output: str) -> Dict[str, Any]:
        raise NotImplementedError("VyOSDevice.parse_version")

    def parse_interfaces(self, output: str) -> List[InterfaceStatus]:
        raise NotImplementedError("VyOSDevice.parse_interfaces")

    def parse_ospf_neighbors(self, output: str) -> List[OspfNeighbor]:
        raise NotImplementedError("VyOSDevice.parse_ospf_neighbors")

    def parse_arp(self, output: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("VyOSDevice.parse_arp")

    def parse_cpu(self, output: str) -> Optional[float]:
        raise NotImplementedError("VyOSDevice.parse_cpu")

    def _apply_config(self, lines: List[str]) -> str:
        output = self._connection.send_config_set(lines, exit_config_mode=False)
        output += self._connection.commit()
        output += self._connection.send_command("save")
        self._connection.exit_config_mode()
        return output
