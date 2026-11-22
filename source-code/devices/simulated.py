"""Simulated MikroTik and VyOS devices that answer with real lab output (tests/samples).

Used by the tests and by ``python main.py --demo ...`` so the whole program,
including the web interface, can be tried without the GNS3 lab. Config
pushes are only recorded, nothing is sent anywhere.
"""

import os
from pathlib import Path

from devices.mikrotik import MikroTikDevice
from devices.vyos import VyOSDevice

SAMPLES = Path(__file__).resolve().parent.parent / "tests" / "samples"


def _read(vendor: str, name: str) -> str:
    return (SAMPLES / vendor / f"{name}.txt").read_text(encoding="utf-8")


STATE_DIR = None  # set by use_simulated_devices(): keeps pushed lines between CLI runs


def _pushed(cls, name):
    if STATE_DIR is not None:
        path = STATE_DIR / f"{name}.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return cls.pushed.get(name, [])


def _record(cls, name, lines):
    cls.pushed.setdefault(name, []).extend(lines)
    if STATE_DIR is not None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_DIR / f"{name}.txt", "a", encoding="utf-8") as fh:
            fh.write("".join(line + "\n" for line in lines))


def _as_export(lines):
    """Show pushed RouterOS commands the way ``/export`` prints them (menu line, then the entry)."""
    out = []
    for line in lines:
        if line.startswith(":if") and "do={" in line:
            line = line.split("do={", 1)[1].rstrip("}")
        for verb in (" set ", " add "):
            if line.startswith("/") and verb in line:
                menu, rest = line.split(verb, 1)
                out += [menu, verb.strip() + " " + rest]
                break
    return "\n".join(out) + ("\n" if out else "")


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
            c["running_config"]: _read("mikrotik", "export") + _as_export(_pushed(type(self), self.name)),
        })

    def _apply_config(self, lines):
        _record(type(self), self.name, lines)
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
            c["running_config"]: "\n".join([_read("vyos", "show_configuration_commands").rstrip()]
                                            + _pushed(type(self), self.name)) + "\n",
        })

    def _apply_config(self, lines):
        _record(type(self), self.name, lines)
        return "ok"


def use_simulated_devices(state_dir: Path) -> None:
    """Make the factory build the simulated classes for the lab device types (whole process).

    Pushed config lines are kept in ``state_dir`` so a later run sees them.
    """
    global STATE_DIR
    from devices.factory import DeviceFactory

    STATE_DIR = Path(state_dir)
    DeviceFactory._registry["mikrotik_routeros"] = FakeMikroTik
    DeviceFactory._registry["vyos"] = FakeVyOS
    os.environ.setdefault("NET_USERNAME", "demo")
    os.environ.setdefault("NET_PASSWORD", "demo")


def use_fake_devices(monkeypatch):
    """Pytest helper: same as above, undone after the test."""
    from devices.factory import DeviceFactory

    monkeypatch.setitem(DeviceFactory._registry, "mikrotik_routeros", FakeMikroTik)
    monkeypatch.setitem(DeviceFactory._registry, "vyos", FakeVyOS)
    monkeypatch.setenv("NET_USERNAME", "admin")
    monkeypatch.setenv("NET_PASSWORD", "test")
    FakeMikroTik.down, FakeVyOS.down = set(), set()
    FakeMikroTik.pushed, FakeVyOS.pushed = {}, {}
