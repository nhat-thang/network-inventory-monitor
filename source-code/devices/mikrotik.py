"""MikroTik RouterOS routers (tested on CHR 7.24.6)."""

import re
from typing import Any, Dict, List, Optional, Tuple

from core.models import InterfaceStatus, LldpNeighbor, OspfNeighbor, RouteEntry
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
            "routes": "/ip route print terse without-paging",
            "lldp": "/ip neighbor print terse without-paging",
            "arp": "/ip arp print terse without-paging",
            "cpu": "/system resource print",
            "memory": "/system resource print",
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

    _ROUTE_PROTOCOLS = {"c": "connected", "s": "static", "o": "ospf", "b": "bgp", "r": "rip",
                        "d": "dhcp", "v": "vpn", "m": "modem"}

    def parse_routes(self, output: str) -> List[RouteEntry]:
        """Parse ``/ip route print terse``; protocol comes from the lowercase flag (c, s, o, b...)."""
        result = []
        for line in output.splitlines():
            flags, fields = terse_line(line)
            if "dst-address" not in fields or "X" in flags:
                continue
            protocol = next((self._ROUTE_PROTOCOLS[f] for f in flags if f in self._ROUTE_PROTOCOLS), "other")
            gateway = fields.get("gateway", "")
            hop, _, iface = gateway.partition("%")
            is_ip = bool(re.fullmatch(r"\d+(\.\d+){3}", hop))
            result.append(RouteEntry(
                prefix=fields["dst-address"],
                protocol=protocol,
                next_hop=hop if is_ip else None,
                interface=iface or (None if is_ip else hop or None),
            ))
        return result

    def parse_lldp(self, output: str) -> List[LldpNeighbor]:
        """Parse ``/ip neighbor print terse`` (neighbors found by LLDP, CDP or MNDP)."""
        result = []
        for line in output.splitlines():
            _, fields = terse_line(line)
            if "interface" not in fields or not fields.get("identity"):
                continue
            result.append(LldpNeighbor(
                local_interface=fields["interface"],
                neighbor=fields["identity"],
                neighbor_port=fields.get("interface-name"),
                platform=fields.get("platform"),
            ))
        return result

    @staticmethod
    def _to_mb(text: str) -> Optional[float]:
        match = re.match(r"([\d.]+)\s*(KiB|MiB|GiB)", text or "")
        if not match:
            return None
        return float(match.group(1)) * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[match.group(2)]

    def parse_memory(self, output: str) -> Dict[str, Optional[float]]:
        """``free-memory`` / ``total-memory`` from ``/system resource print``."""
        data = key_value_block(output)
        total, free = self._to_mb(data.get("total-memory", "")), self._to_mb(data.get("free-memory", ""))
        if not total or free is None:
            return {"total_mb": total, "used_percent": None}
        return {"total_mb": round(total, 1), "used_percent": round((total - free) / total * 100, 1)}

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

    @staticmethod
    def _export_entries(text: str) -> List[Tuple[str, str]]:
        """``/export`` text -> [(section, "add ..." | "set ...")], wrapped lines joined."""
        joined = re.sub(r"\\\n\s*", "", text)
        entries: List[Tuple[str, str]] = []
        section = ""
        for raw in joined.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("/"):
                section = line
            elif line.startswith(("add ", "set ")) and section:
                entries.append((section, line))
        return entries

    def rollback_commands(self, current: str, target: str) -> List[str]:
        """Diff two ``/export`` outputs into RouterOS commands.

        - ``add`` entries only in ``current`` are removed (newest first) with
          ``remove [find <same fields>]``;
        - ``add`` and ``set`` entries only in ``target`` are applied again.
        A ``set`` that exists only in ``current`` cannot be undone without
        knowing the default value, so it is left as is.
        """
        now, wanted = self._export_entries(current), self._export_entries(target)
        wanted_set, now_set = set(wanted), set(now)
        commands = [
            f"{section} remove [find {line[4:]}]"
            for section, line in reversed(now)
            if line.startswith("add ") and (section, line) not in wanted_set
        ]
        commands += [f"{section} {line}" for section, line in wanted if (section, line) not in now_set]
        return commands

    def _apply_config(self, lines: List[str]) -> str:
        # RouterOS applies every command immediately and saves it automatically.
        output = []
        for line in lines:
            reply = self._connection.send_command(line, expect_string=r"\] >", cmd_verify=False)
            if re.search(r"failure:|syntax error|bad command|expected |no such item|input does not match", reply):
                raise RuntimeError(f"{line!r}: {reply.strip()}")
            output.append(f"{line}\n{reply}")
        return "\n".join(output)
