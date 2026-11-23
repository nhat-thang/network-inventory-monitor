"""Tests for the YAML inventory (no network needed)."""

import pytest

from core.exceptions import InventoryError
from devices import MikroTikDevice, VyOSDevice
from inventory import Inventory

YAML = """
devices:
  - {name: R1, host: 192.168.100.11, device_type: mikrotik_routeros, group: core, tags: [mikrotik, ospf]}
  - {name: VY1, host: 192.168.100.21, device_type: vyos, group: core, role: router, tags: [vyos]}
  - {name: VY9, host: 192.168.100.29, device_type: vyos, group: lab, credentials: LAB}
"""


@pytest.fixture
def inv(tmp_path):
    path = tmp_path / "inventory.yaml"
    path.write_text(YAML, encoding="utf-8")
    return Inventory(path).load()


def test_load_and_defaults(inv):
    assert len(inv) == 3
    assert inv.get("R1")["port"] == 22
    assert inv.get("VY9")["tags"] == []


def test_filter_by_group_role_and_tag(inv):
    assert [r["name"] for r in inv.filter(group="core")] == ["R1", "VY1"]
    assert [r["name"] for r in inv.filter(role="router")] == ["VY1"]
    assert [r["name"] for r in inv.filter(group="core", tag="mikrotik")] == ["R1"]
    assert inv.filter(tag="nothing") == []


def test_add_update_remove_and_save(inv):
    inv.add({"name": "VY2", "host": "192.168.100.22", "device_type": "vyos", "tags": "vyos, ospf"})
    inv.update("VY2", group="core", port=2222)
    inv.remove("VY9")
    inv.save()
    reloaded = Inventory(inv.path).load()
    assert [r["name"] for r in reloaded.records] == ["R1", "VY1", "VY2"]
    assert reloaded.get("VY2") == {"name": "VY2", "host": "192.168.100.22", "port": 2222,
                                   "device_type": "vyos", "group": "core", "tags": ["vyos", "ospf"]}


@pytest.mark.parametrize("record, message", [
    ({"name": "R1", "host": "192.168.100.99", "device_type": "vyos"}, "already exists"),
    ({"name": "X", "device_type": "vyos"}, "missing field"),
    ({"name": "X", "host": "not-an-ip", "device_type": "vyos"}, "invalid host"),
    ({"name": "X", "host": "10.0.0.1", "device_type": "junos"}, "unsupported device_type"),
    ({"name": "X", "host": "10.0.0.1", "device_type": "vyos", "port": 70000}, "invalid port"),
    ({"name": "X", "host": "10.0.0.1", "device_type": "vyos", "colour": "red"}, "unknown field"),
])
def test_invalid_records_are_rejected(inv, record, message):
    with pytest.raises(InventoryError, match=message):
        inv.add(record)


def test_unknown_device_and_missing_file(inv, tmp_path):
    with pytest.raises(InventoryError, match="Unknown device"):
        inv.remove("NOPE")
    with pytest.raises(InventoryError, match="not found"):
        Inventory(tmp_path / "missing.yaml").load()


def test_build_devices_uses_factory_and_per_device_credentials(inv, monkeypatch):
    monkeypatch.setenv("NET_USERNAME", "admin")
    monkeypatch.setenv("NET_PASSWORD", "pw")
    monkeypatch.setenv("LAB_USERNAME", "lab")
    monkeypatch.setenv("LAB_PASSWORD", "pw2")
    devices = inv.build_devices()
    assert [type(d) for d in devices] == [MikroTikDevice, VyOSDevice, VyOSDevice]
    assert devices[0].host == "192.168.100.11"
