"""Simulated MikroTik and VyOS devices that answer with real lab output (tests/samples).

Used by the service and web tests so the whole flow runs without the GNS3 lab.
"""

from pathlib import Path

from devices import MikroTikDevice, VyOSDevice

SAMPLES = Path(__file__).parent / "samples"


def _read(vendor: str, name: str) -> str:
    return (SAMPLES / vendor / f"{name}.txt").read_text(encoding="utf-8")


class _Session:
    def __init__(self, replies):
        self.replies = replies

    def send_command(self, command, **_):
        return self.replies.get(command, "")

    def disconnect(self):
        pass


class FakeMikroTik(MikroTikDevice):
    """R1/R2 answering with the saved RouterOS output; config pushes are recorded."""

    down = set()       # device names that time out
    pushed = {}        # name -> list of pushed lines

    def connect(self):
        from core.exceptions import DeviceTimeoutError

        if self.name in self.down:
            raise DeviceTimeoutError(f"{self.name}: no response from {self.host}")
        c = self.commands
        self._connection = _Session({
            c["version"]: _read("mikrotik", "system_resource"),
            c["identity"]: f"name: {self.name}-MikroTik",
            c["license"]: _read("mikrotik", "system_license"),
            c["interfaces"]: _read("mikrotik", "interface_terse"),
            c["ip_addresses"]: _read("mikrotik", "ip_address_terse"),
            c["ospf_neighbors"]: _read("mikrotik", "ospf_neighbor_full"),
            c["routes"]: _read("mikrotik", "ip_route_terse"),
            c["lldp"]: _read("mikrotik", "ip_neighbor_terse"),
            c["arp"]: _read("mikrotik", "ip_arp_terse"),
            c["running_config"]: _read("mikrotik", "export"),
        })

    def _apply_config(self, lines):
        self.pushed.setdefault(self.name, []).extend(lines)
        return "ok"


class FakeVyOS(VyOSDevice):
    """VY1/VY2 answering with the saved VyOS output."""

    down = set()
    pushed = {}

    def connect(self):
        from core.exceptions import DeviceTimeoutError

        if self.name in self.down:
            raise DeviceTimeoutError(f"{self.name}: no response from {self.host}")
        c = self.commands
        self._connection = _Session({
            c["version"]: _read("vyos", "show_version"),
            c["hostname"]: f"{self.name}-VyOS",
            c["uptime"]: _read("vyos", "show_system_uptime"),
            c["interfaces"]: _read("vyos", "show_interfaces"),
            c["ospf_neighbors"]: _read("vyos", "show_ip_ospf_neighbor_full"),
            c["routes"]: _read("vyos", "show_ip_route"),
            c["lldp"]: _read("vyos", "show_lldp_neighbors_off"),
            c["memory"]: _read("vyos", "show_system_memory"),
            c["arp"]: _read("vyos", "show_arp"),
            c["running_config"]: _read("vyos", "show_configuration_commands"),
        })

    def _apply_config(self, lines):
        self.pushed.setdefault(self.name, []).extend(lines)
        return "ok"


def use_fake_devices(monkeypatch):
    """Make the factory build the fake classes for the lab device types."""
    from devices.factory import DeviceFactory

    monkeypatch.setitem(DeviceFactory._registry, "mikrotik_routeros", FakeMikroTik)
    monkeypatch.setitem(DeviceFactory._registry, "vyos", FakeVyOS)
    monkeypatch.setenv("NET_USERNAME", "admin")
    monkeypatch.setenv("NET_PASSWORD", "test")
    FakeMikroTik.down, FakeVyOS.down = set(), set()
    FakeMikroTik.pushed, FakeVyOS.pushed = {}, {}
