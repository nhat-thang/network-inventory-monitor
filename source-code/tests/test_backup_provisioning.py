"""Tests for backup/diff/rollback and template provisioning (no network needed)."""

from pathlib import Path

import pytest

from backup import BackupManager
from backup.backup_manager import BackupError
from core.credentials import Credentials
from core.exceptions import ConfigPushError
from devices import CiscoIOSDevice, MikroTikDevice, VyOSDevice
from provisioning import ConfigPusher
from provisioning.config_pusher import TemplateError

CREDS = Credentials("admin", "pw")
TEMPLATES = Path(__file__).resolve().parents[1] / "provisioning" / "templates"
VYOS_BASE = "set interfaces ethernet eth0 address '192.168.100.21/24'\nset service ssh port '22'\n"


class FakeVyOS(VyOSDevice):
    """VyOS whose running config lives in memory; ``fail_on`` makes a push fail."""

    def __init__(self, config=VYOS_BASE, fail_on=None):
        super().__init__("VY1", "192.0.2.21", CREDS)
        self.config = config
        self.fail_on = fail_on
        self.pushed = []
        self._connection = object()  # pretend the SSH session is open

    def backup_config(self):
        return self.config

    def _apply_config(self, lines):
        self.pushed.append(list(lines))
        if self.fail_on and any(self.fail_on in line for line in lines):
            raise RuntimeError("Commit failed")
        current = self.config.splitlines()
        for line in lines:
            if line.startswith("delete "):
                current = [c for c in current if c != "set " + line[7:]]
            elif line not in current:
                current.append(line)
        self.config = "\n".join(current) + "\n"
        return "ok"


@pytest.fixture
def manager(tmp_path):
    return BackupManager(tmp_path / "backups")


def test_backup_files_are_timestamped_and_listed(manager):
    device = FakeVyOS()
    first, second = manager.backup(device), manager.backup(device)
    assert first != second and first.parent.name == "VY1"
    assert manager.list_backups("VY1") == [first, second]
    assert manager.list_backups("NOPE") == []


def test_diff_shows_only_changes(manager):
    device = FakeVyOS()
    old = manager.backup(device)
    device.config += "set protocols ospf parameters router-id '3.3.3.3'\n"
    new = manager.backup(device)
    diff = manager.diff(old, new)
    assert "+set protocols ospf parameters router-id '3.3.3.3'" in diff
    assert manager.diff(old, old) == ""
    with pytest.raises(BackupError):
        manager.diff(old, old.parent / "missing.cfg")


def test_rollback_returns_device_to_saved_config(manager):
    device = FakeVyOS()
    saved = manager.backup(device)
    device.config += "set protocols ospf area 0 network '10.0.13.0/30'\n"
    manager.rollback(device, saved)
    assert device.config.splitlines() == VYOS_BASE.splitlines()
    assert manager.rollback(device, saved) == "Nothing to roll back."


def test_vyos_rollback_never_touches_passwords():
    vyos = VyOSDevice("VY1", "192.0.2.21", CREDS)
    current = VYOS_BASE + "set system login user admin authentication encrypted-password 'x'\n"
    assert vyos.rollback_commands(current, VYOS_BASE) == []


def test_mikrotik_rollback_commands_from_export():
    mikrotik = MikroTikDevice("R1", "192.0.2.11", CREDS)
    target = (Path(__file__).parent / "samples" / "mikrotik" / "export.txt").read_text(encoding="utf-8")
    current = target.replace(
        "/ip dhcp-client",
        "add address=10.0.12.1/30 comment=ospf-link interface=ether2 network=\\\n    10.0.12.0\n"
        "/routing ospf instance\nadd disabled=no name=default-v2 router-id=1.1.1.1\n/ip dhcp-client")
    assert mikrotik.rollback_commands(current, target) == [
        "/routing ospf instance remove [find disabled=no name=default-v2 router-id=1.1.1.1]",
        "/ip address remove [find address=10.0.12.1/30 comment=ospf-link interface=ether2 network=10.0.12.0]",
    ]
    assert mikrotik.rollback_commands(target, current)[0].startswith("/ip address add address=10.0.12.1/30")


def test_cisco_rollback_is_reported_as_unsupported(manager, tmp_path):
    saved = tmp_path / "r.cfg"
    saved.write_text("hostname R9\n", encoding="utf-8")

    class FakeCisco(CiscoIOSDevice):
        def backup_config(self):
            return "hostname R9\n"

    with pytest.raises(NotImplementedError):
        manager.rollback(FakeCisco("R9", "192.0.2.9", CREDS), saved)


# ------------------------------------------------------------- provisioning
VARS = {"router_id": "3.3.3.3", "interfaces": [{"name": "eth1", "address": "10.0.13.2/30"}]}


def test_render_derives_addresses_per_vendor(manager):
    pusher = ConfigPusher(TEMPLATES, manager)
    assert pusher.render(FakeVyOS(), "vyos", VARS) == [
        "set interfaces ethernet eth1 address 10.0.13.2/30",
        "set protocols ospf area 0 network 10.0.13.0/30",
        "set protocols ospf parameters router-id 3.3.3.3",
    ]
    mikrotik = pusher.render(MikroTikDevice("R1", "192.0.2.11", CREDS), "mikrotik_routeros",
                             {"router_id": "1.1.1.1", "interfaces": [{"name": "ether2", "address": "10.0.12.1/30"}]})
    assert all(line.startswith(":if") for line in mikrotik)
    assert "networks=10.0.12.0/30" in mikrotik[-1]
    cisco = pusher.render(CiscoIOSDevice("R9", "192.0.2.9", CREDS), "cisco_ios", VARS)
    assert " ip address 10.0.13.2 255.255.255.252" in cisco


@pytest.mark.parametrize("device_type, variables, message", [
    ("junos", VARS, "no template"),
    ("vyos", {"router_id": "1.1.1.1", "interfaces": [{"name": "eth1", "address": "10.0.13.300/30"}]}, "bad interface"),
    ("vyos", {"interfaces": []}, "cannot render"),
])
def test_render_errors(manager, device_type, variables, message):
    with pytest.raises(TemplateError, match=message):
        ConfigPusher(TEMPLATES, manager).render(FakeVyOS(), device_type, variables)


def test_deploy_dry_run_changes_nothing(manager):
    device = FakeVyOS()
    out = ConfigPusher(TEMPLATES, manager).deploy(device, ["set a"], dry_run=True)
    assert out == "set a" and device.pushed == [] and manager.list_backups("VY1") == []


def test_deploy_backs_up_then_applies(manager):
    device = FakeVyOS()
    pusher = ConfigPusher(TEMPLATES, manager)
    pusher.deploy(device, pusher.render(device, "vyos", VARS))
    assert "set protocols ospf parameters router-id 3.3.3.3" in device.config
    assert len(manager.list_backups("VY1")) == 1


def test_deploy_rolls_back_when_push_fails(manager):
    device = FakeVyOS(fail_on="router-id")
    pusher = ConfigPusher(TEMPLATES, manager)
    with pytest.raises(ConfigPushError, match="rolled back"):
        pusher.deploy(device, pusher.render(device, "vyos", VARS))
    assert device.config == VYOS_BASE
