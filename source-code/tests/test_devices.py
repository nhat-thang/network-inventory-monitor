"""Tests for the device hierarchy, factory and credentials (no network needed)."""

import pytest

from core.connection_manager import ConnectionManager
from core.credentials import Credentials
from core.exceptions import DeviceTimeoutError, UnsupportedDeviceError
from devices import CiscoIOSDevice, DeviceFactory, NetworkDevice, VyOSDevice

CREDS = Credentials("admin", "secret-password")


def record(name, device_type):
    return {"name": name, "host": "192.0.2.1", "device_type": device_type, "group": "core"}


def test_factory_builds_the_right_subclass():
    assert isinstance(DeviceFactory.create(record("R1", "cisco_ios"), CREDS), CiscoIOSDevice)
    assert isinstance(DeviceFactory.create(record("VY1", "vyos"), CREDS), VyOSDevice)


def test_factory_rejects_unknown_type():
    with pytest.raises(UnsupportedDeviceError):
        DeviceFactory.create(record("X", "unknown_os"), CREDS)


def test_polymorphism_same_call_different_behaviour():
    devices = [DeviceFactory.create(record("R1", "cisco_ios"), CREDS),
               DeviceFactory.create(record("VY1", "vyos"), CREDS)]
    backup_commands = {d.vendor: d.commands["running_config"] for d in devices}
    assert backup_commands == {"Cisco IOS": "show running-config",
                               "VyOS": "show configuration commands"}


def test_dry_run_does_not_need_a_connection():
    device = DeviceFactory.create(record("R1", "cisco_ios"), CREDS)
    assert device.push_config(["router ospf 1"], dry_run=True) == "router ospf 1"


def test_credentials_hide_the_password():
    assert "secret-password" not in repr(CREDS)
    assert "secret-password" not in str(CREDS)


def test_credentials_from_env(monkeypatch):
    monkeypatch.setenv("TEST_USERNAME", "u")
    monkeypatch.setenv("TEST_PASSWORD", "p")
    creds = Credentials.from_env("TEST")
    assert (creds.username, creds.password) == ("u", "p")


class _FakeDevice(CiscoIOSDevice):
    """Cisco device whose SSH session is simulated."""

    def connect(self):
        if self.name == "DOWN":
            raise DeviceTimeoutError("DOWN: no response")
        self._connection = object()

    def disconnect(self):
        self._connection = None


def test_one_failed_device_does_not_stop_the_others():
    devices = [_FakeDevice("R1", "192.0.2.1", CREDS), _FakeDevice("DOWN", "192.0.2.2", CREDS)]
    results = {r.device: r for r in ConnectionManager(max_workers=2).run(devices, lambda d: d.name)}
    assert results["R1"].success and results["R1"].result == "R1"
    assert not results["DOWN"].success and "DeviceTimeoutError" in results["DOWN"].error


def test_network_device_is_abstract():
    with pytest.raises(TypeError):
        NetworkDevice("X", "192.0.2.1", CREDS)  # type: ignore[abstract]
