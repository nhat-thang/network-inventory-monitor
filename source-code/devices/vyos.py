"""VyOS routers (tested on VyOS 2026.11.18 rolling)."""

import re
from typing import Any, Dict, List, Optional

from core.models import InterfaceStatus, LldpNeighbor, OspfNeighbor, RouteEntry
from devices.base import NetworkDevice
from devices.factory import DeviceFactory
from devices.parsing import duration_to_seconds, key_value_block

_IPV4_PREFIX = re.compile(r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$")
_MAC = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", re.IGNORECASE)


@DeviceFactory.register("vyos")
class VyOSDevice(NetworkDevice):
    """VyOS platform (configuration needs an explicit commit and save).

    ``show version`` has no hostname or uptime, so ``collect_version`` also
    runs ``show host name`` and ``show system uptime``.
    """

    @property
    def vendor(self) -> str:
        return "VyOS"

    @property
    def netmiko_device_type(self) -> str:
        return "vyos"

    @property
    def commands(self) -> Dict[str, str]:
        return {
            "version": "show version",
            "hostname": "show host name",
            "uptime": "show system uptime",
            "interfaces": "show interfaces",
            "ospf_neighbors": "show ip ospf neighbor",
            "routes": "show ip route",
            "lldp": "show lldp neighbors detail",
            "arp": "show arp",
            "cpu": "show system uptime",
            "memory": "show system memory",
            "running_config": "show configuration commands",
        }

    # ----------------------------------------------------------------- hooks
    def collect_version(self) -> Dict[str, Any]:
        cmd = self.commands
        info = self.parse_version(self.send_command(cmd["version"]))
        hostname = self.send_command(cmd["hostname"]).strip().splitlines()
        info["hostname"] = hostname[-1].strip() if hostname else None
        info["uptime_seconds"] = self.parse_uptime(self.send_command(cmd["uptime"]))
        return info

    # --------------------------------------------------------------- parsers
    def parse_version(self, output: str) -> Dict[str, Any]:
        """Parse ``show version`` (version string and hardware serial)."""
        data = key_value_block(output)
        serial = data.get("hardware s/n") or data.get("hardware uuid") or None
        return {
            "hostname": None,
            "os_version": data.get("version"),
            "serial": serial,
            "uptime_seconds": None,
        }

    @staticmethod
    def parse_uptime(output: str) -> Optional[int]:
        """Parse the ``Uptime:`` line of ``show system uptime``."""
        match = re.search(r"uptime:\s*(.+)", output, re.IGNORECASE)
        return duration_to_seconds(match.group(1)) if match else None

    def parse_interfaces(self, output: str) -> List[InterfaceStatus]:
        """Parse the ``show interfaces`` table (``S/L`` column: u/u, u/D, A/D)."""
        result: List[InterfaceStatus] = []
        for line in output.splitlines():
            columns = line.split()
            if len(columns) < 2 or line[0].isspace() or columns[0] in ("Codes:", "Interface"):
                continue
            if set(columns[0]) == {"-"}:
                continue
            state = next((c for c in columns if re.fullmatch(r"[uAD]/[uD]", c)), None)
            if state is None:
                continue
            admin, link = state.split("/")
            ip = columns[1] if _IPV4_PREFIX.match(columns[1]) else None
            result.append(
                InterfaceStatus(
                    name=columns[0],
                    ip_address=ip,
                    admin_up=admin != "A",
                    oper_up=admin == "u" and link == "u",
                )
            )
        return result

    def parse_ospf_neighbors(self, output: str) -> List[OspfNeighbor]:
        """Parse FRR ``show ip ospf neighbor``.

        ``Neighbor ID  Pri State  Up Time  Dead Time Address  Interface ...``
        """
        result = []
        for line in output.splitlines():
            columns = line.split()
            if len(columns) < 6 or not re.fullmatch(r"\d+(\.\d+){3}", columns[0]):
                continue
            addresses = [c for c in columns[3:] if re.fullmatch(r"\d+(\.\d+){3}", c)]
            interface = next((c.split(":")[0] for c in columns if ":" in c and "/" not in c
                              and not re.search(r"\d+[hms]", c)), "")
            result.append(
                OspfNeighbor(
                    neighbor_id=columns[0],
                    address=addresses[0] if addresses else "",
                    interface=interface,
                    state=columns[2].split("/")[0],
                )
            )
        return result

    _ROUTE_CODES = {"K": "kernel", "C": "connected", "L": "local", "S": "static", "O": "ospf",
                    "B": "bgp", "R": "rip", "I": "isis"}
    _ROUTE_LINE = re.compile(r"^([A-Za-z])[>*=q ]*\s+(\d+(?:\.\d+){3}/\d+)\s+(.*)$")

    def parse_routes(self, output: str) -> List[RouteEntry]:
        """Parse FRR ``show ip route`` (first line of each prefix; ECMP lines are skipped)."""
        result = []
        for line in output.splitlines():
            match = self._ROUTE_LINE.match(line)
            if not match:
                continue
            code, prefix, rest = match.groups()
            via = re.search(r"via (\d+(?:\.\d+){3})", rest)
            iface = re.search(r"(?:connected|\d), ([\w.@-]+)", rest)
            result.append(RouteEntry(
                prefix=prefix,
                protocol=self._ROUTE_CODES.get(code, "other"),
                next_hop=via.group(1) if via else None,
                interface=iface.group(1) if iface else None,
            ))
        return result

    def parse_lldp(self, output: str) -> List[LldpNeighbor]:
        """Parse LLDP neighbours.

        Handles the lldpcli detail format (``Interface: eth1, via: LLDP`` blocks
        with ``SysName``/``PortID``/``SysDescr``) and, as a fallback, the
        summary table whose header is ``Device ID ... Port ID``.
        """
        if re.search(r"^\s*Interface:", output, re.MULTILINE):
            return self._parse_lldp_detail(output)
        return self._parse_lldp_table(output)

    @staticmethod
    def _parse_lldp_detail(output: str) -> List[LldpNeighbor]:
        result = []
        for block in re.split(r"^\s*Interface:\s*", output, flags=re.MULTILINE)[1:]:
            local = block.split(",", 1)[0].strip()
            name = re.search(r"SysName:\s*(.+)", block)
            port = re.search(r"PortID:\s*(?:ifname|local|mac|ifalias)?\s*(.+)", block)
            descr = re.search(r"SysDescr:\s*(.+)", block)
            if not name:
                continue
            result.append(LldpNeighbor(local_interface=local, neighbor=name.group(1).strip(),
                                       neighbor_port=port.group(1).strip() if port else None,
                                       platform=descr.group(1).strip() if descr else None))
        return result

    @staticmethod
    def _parse_lldp_table(output: str) -> List[LldpNeighbor]:
        lines = output.splitlines()
        header = next((i for i, l in enumerate(lines) if "Device ID" in l and "Port" in l), None)
        if header is None:
            return []
        head = lines[header]
        titles = ["Device ID", "Local", "Proto", "Cap", "Platform", "Port"]
        found = [(t, head.find(t)) for t in titles if head.find(t) >= 0]
        found.sort(key=lambda x: x[1])
        starts = [pos for _, pos in found]
        names = [t for t, _ in found]
        result = []
        for line in lines[header + 1:]:
            if not line.strip() or set(line.strip()) <= {"-", " "}:
                continue
            cols = dict(zip(names, (line[a:b].strip() for a, b in zip(starts, starts[1:] + [None]))))
            if not cols.get("Device ID"):
                continue
            result.append(LldpNeighbor(local_interface=cols.get("Local", ""), neighbor=cols["Device ID"],
                                       neighbor_port=cols.get("Port") or None, platform=cols.get("Platform") or None))
        return result

    def parse_memory(self, output: str) -> Dict[str, Optional[float]]:
        """``show system memory``: ``Total: 974.73 MB`` / ``Used: 514.25 MB``."""
        total = re.search(r"Total:\s*([\d.]+)\s*MB", output)
        used = re.search(r"Used:\s*([\d.]+)\s*MB", output)
        if not total:
            return {"total_mb": None, "used_percent": None}
        total_mb = float(total.group(1))
        percent = round(float(used.group(1)) / total_mb * 100, 1) if used and total_mb else None
        return {"total_mb": total_mb, "used_percent": percent}

    def parse_arp(self, output: str) -> List[Dict[str, Any]]:
        """Parse ``show arp`` (``Address  Interface  Link layer address  State``)."""
        result = []
        for line in output.splitlines():
            columns = line.split()
            if len(columns) < 3 or not re.fullmatch(r"\d+(\.\d+){3}", columns[0]):
                continue
            mac = next((c for c in columns if _MAC.match(c)), None)
            if mac is None:
                continue
            result.append({"ip": columns[0], "mac": mac.lower(), "interface": columns[1]})
        return result

    def parse_cpu(self, output: str) -> Optional[float]:
        """Use the 1-minute load average from ``show system uptime`` as CPU %."""
        match = re.search(r"1\s+minute:\s*(\d+(?:\.\d+)?)\s*%", output)
        return float(match.group(1)) if match else None

    # ---------------------------------------------------------------- config
    _NEVER_TOUCH = ("authentication", "login user")

    def rollback_commands(self, current: str, target: str) -> List[str]:
        """Diff two ``show configuration commands`` outputs into delete/set commands.

        Lines only in ``current`` are deleted (newest first), lines only in
        ``target`` are set again. Login/password lines are never touched.
        """
        def lines(text: str) -> List[str]:
            return [line.strip() for line in text.splitlines()
                    if line.strip().startswith("set ") and not any(k in line for k in self._NEVER_TOUCH)]

        now, wanted = lines(current), lines(target)
        wanted_set, now_set = set(wanted), set(now)
        deletes = ["delete " + line[4:] for line in reversed(now) if line not in wanted_set]
        sets = [line for line in wanted if line not in now_set]
        return deletes + sets

    def _apply_config(self, lines: List[str]) -> str:
        output = self._connection.send_config_set(lines, exit_config_mode=False)
        output += self._connection.commit()
        output += self._connection.send_command("save", expect_string=r"#")
        self._connection.exit_config_mode()
        if re.search(r"Commit failed|Set failed|Invalid command", output):
            raise RuntimeError(output.strip()[-500:])
        return output
