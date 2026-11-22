"""Parser tests on real output saved from the GNS3 lab (tests/samples/).

Lines marked "synthetic" were written by hand because the state did not exist
in the lab yet (OSPF not configured, a disabled or broken interface).
"""

from pathlib import Path

import pytest

from core.credentials import Credentials
from core.models import InterfaceStatus, LldpNeighbor, OspfNeighbor, RouteEntry
from devices import CiscoIOSDevice, MikroTikDevice, VyOSDevice
from devices.parsing import clean_output, duration_to_seconds, terse_line

SAMPLES = Path(__file__).parent / "samples"
CREDS = Credentials("admin", "pw")


def sample(vendor: str, name: str) -> str:
    return (SAMPLES / vendor / f"{name}.txt").read_text(encoding="utf-8")


class FakeSession:
    """Stands in for the Netmiko session: returns saved output per command."""

    def __init__(self, replies):
        self.replies = replies

    def send_command(self, command, **_):
        return self.replies[command]

    def disconnect(self):
        pass


# ------------------------------------------------------------------ helpers
@pytest.mark.parametrize("text, seconds", [
    ("1m6s", 66), ("1w2d3h4m5s", 788645), ("44s", 44), ("0h 25m 42s", 1542),
    ("1 week, 2 days, 3 hours, 4 minutes", 788640), ("", None), ("never", None),
])
def test_duration_to_seconds(text, seconds):
    assert duration_to_seconds(text) == seconds


def test_clean_output_removes_terminal_codes():
    assert clean_output("\x1b[?2004l\r\nVY1-VyOS  \r\n") == "VY1-VyOS"


def test_terse_line_flags_fields_and_comment():
    assert terse_line("0 DC address=1.1.1.1 mac-address=AA") == ("DC", {"address": "1.1.1.1", "mac-address": "AA"})
    assert terse_line('3   name="ether4" type=ether') == ("", {"name": "ether4", "type": "ether"})
    assert terse_line("0 X ;;; old link address=1.1.1.1/30")[1]["comment"] == "old link"


# ----------------------------------------------------------------- MikroTik
@pytest.fixture
def mikrotik():
    return MikroTikDevice("R1", "192.168.100.11", CREDS)


def test_mikrotik_version_and_cpu(mikrotik):
    out = sample("mikrotik", "system_resource")
    assert mikrotik.parse_version(out) == {
        "hostname": None, "os_version": "RouterOS 7.24.6 (long-term)", "serial": None, "uptime_seconds": 66}
    assert mikrotik.parse_cpu(out) == 1.0


def test_mikrotik_interfaces_and_addresses(mikrotik):
    interfaces = mikrotik.parse_interfaces(sample("mikrotik", "interface_terse"))
    assert [i.name for i in interfaces] == [f"ether{n}" for n in range(1, 9)] + ["lo"]
    assert interfaces[0] == InterfaceStatus("ether1", None, admin_up=True, oper_up=True)
    assert interfaces[3] == InterfaceStatus("ether4", None, admin_up=True, oper_up=False)
    assert mikrotik.parse_ip_addresses(sample("mikrotik", "ip_address_terse")) == {"ether1": "192.168.100.11/24"}


def test_mikrotik_disabled_interface_is_admin_down(mikrotik):
    out = "5 X  name=ether6 default-name=ether6 type=ether mtu=1500"  # synthetic
    assert mikrotik.parse_interfaces(out) == [InterfaceStatus("ether6", None, False, False)]


def test_mikrotik_arp_and_ospf(mikrotik):
    assert mikrotik.parse_arp(sample("mikrotik", "ip_arp_terse")) == [
        {"ip": "192.168.100.1", "mac": "00:50:56:c0:00:03", "interface": "ether1"}]
    assert mikrotik.parse_ospf_neighbors(sample("mikrotik", "ospf_neighbor_terse")) == []
    synthetic = ('0 instance=default-v2 area=backbone address=10.0.12.2 priority=1 router-id=2.2.2.2 '
                 'state="Full" state-changes=6 adjacency=3m12s timeout=37s')
    neighbor = mikrotik.parse_ospf_neighbors(synthetic)[0]
    assert (neighbor.neighbor_id, neighbor.address, neighbor.state) == ("2.2.2.2", "10.0.12.2", "Full")


def test_mikrotik_get_facts_end_to_end(mikrotik):
    cmd = mikrotik.commands
    mikrotik._connection = FakeSession({
        cmd["version"]: sample("mikrotik", "system_resource"),
        cmd["identity"]: sample("mikrotik", "system_identity"),
        cmd["license"]: sample("mikrotik", "system_license"),
        cmd["interfaces"]: sample("mikrotik", "interface_terse"),
        cmd["ip_addresses"]: sample("mikrotik", "ip_address_terse"),
        cmd["ospf_neighbors"]: sample("mikrotik", "ospf_neighbor_terse"),
        cmd["routes"]: sample("mikrotik", "ip_route_terse"),
        cmd["lldp"]: sample("mikrotik", "ip_neighbor_terse"),
        cmd["arp"]: sample("mikrotik", "ip_arp_terse"),
        cmd["running_config"]: sample("mikrotik", "export"),
    })
    facts = mikrotik.get_facts()
    assert (facts.hostname, facts.serial, facts.uptime_seconds, facts.cpu_percent) == (
        "R1-MikroTik", "pNwYzAOYZKB", 66, 1.0)
    assert facts.interfaces[0].ip_address == "192.168.100.11/24"
    assert sum(i.admin_up and not i.oper_up for i in facts.interfaces) == 5
    assert len(facts.config_hash) == 64


def test_mikrotik_backup_ignores_export_timestamp(mikrotik):
    text = sample("mikrotik", "export")
    mikrotik._connection = FakeSession({"/export": text})
    first = mikrotik.backup_config()
    mikrotik._connection = FakeSession({"/export": text.replace("01:30:00", "09:15:00")})
    assert mikrotik.backup_config() == first and "by RouterOS" not in first


# --------------------------------------------------------------------- VyOS
@pytest.fixture
def vyos():
    return VyOSDevice("VY1", "192.168.100.21", CREDS)


def test_vyos_version_uptime_cpu(vyos):
    assert vyos.parse_version(sample("vyos", "show_version")) == {
        "hostname": None, "os_version": "VyOS 2026.11.18-0016-rolling",
        "serial": "fa34e875-1e73-421b-ac99-9afa6eac45a5", "uptime_seconds": None}
    uptime = sample("vyos", "show_system_uptime")
    assert vyos.parse_uptime(uptime) == 44
    assert vyos.parse_cpu(uptime) == 70.0


def test_vyos_interfaces(vyos):
    assert vyos.parse_interfaces(sample("vyos", "show_interfaces")) == [
        InterfaceStatus("eth0", "192.168.100.21/24", True, True),
        InterfaceStatus("eth1", None, True, True),
        InterfaceStatus("eth2", None, True, True),
        InterfaceStatus("lo", "127.0.0.1/8", True, True),
    ]
    synthetic = ("eth1         10.0.13.2/30       0c:34:e8:75:00:01  default   1500  u/D\n"
                 "eth2         -                  0c:34:e8:75:00:02  default   1500  A/D  uplink")
    assert vyos.parse_interfaces(synthetic) == [
        InterfaceStatus("eth1", "10.0.13.2/30", True, False),
        InterfaceStatus("eth2", None, False, False)]


def test_vyos_arp_and_ospf(vyos):
    assert vyos.parse_arp(sample("vyos", "show_arp")) == [
        {"ip": "192.168.100.1", "mac": "00:50:56:c0:00:03", "interface": "eth0"}]
    assert vyos.parse_arp("192.168.100.9  eth0  <incomplete>  FAILED") == []  # synthetic

    assert vyos.parse_ospf_neighbors(sample("vyos", "show_ip_ospf_neighbor")) == []
    synthetic_ospf = (
        "Neighbor ID     Pri State           Up Time         Dead Time Address         Interface"
        "                        RXmtL RqstL DBsmL\n"
        "1.1.1.1           1 Full/DR         3m12s             37.001s 10.0.13.1       eth1:10.0.13.2"
        "                       0     0     0")
    neighbor = vyos.parse_ospf_neighbors(synthetic_ospf)[0]
    assert (neighbor.neighbor_id, neighbor.address, neighbor.interface, neighbor.state) == (
        "1.1.1.1", "10.0.13.1", "eth1", "Full")


def test_vyos_get_facts_end_to_end(vyos):
    cmd = vyos.commands
    vyos._connection = FakeSession({
        cmd["version"]: sample("vyos", "show_version"),
        cmd["hostname"]: "\x1b[?2004l\r\nVY1-VyOS",
        cmd["uptime"]: sample("vyos", "show_system_uptime"),
        cmd["interfaces"]: sample("vyos", "show_interfaces"),
        cmd["ospf_neighbors"]: sample("vyos", "show_ip_ospf_neighbor_full"),
        cmd["routes"]: sample("vyos", "show_ip_route"),
        cmd["lldp"]: sample("vyos", "show_lldp_neighbors_off"),
        cmd["memory"]: sample("vyos", "show_system_memory"),
        cmd["arp"]: sample("vyos", "show_arp"),
        cmd["running_config"]: sample("vyos", "show_configuration_commands"),
    })
    facts = vyos.get_facts()
    assert (facts.hostname, facts.uptime_seconds, facts.cpu_percent) == ("VY1-VyOS", 44, 70.0)
    assert (facts.memory_total_mb, facts.memory_percent) == (974.73, 55.8)
    assert len(facts.routes) == 8 and len(facts.ospf_neighbors) == 2 and facts.lldp_neighbors == []
    assert all(i.oper_up for i in facts.interfaces)


# -------------------------------------------------------------------- Cisco
def test_cisco_parsers_with_textfsm():
    cisco = CiscoIOSDevice("R9", "192.0.2.9", CREDS)
    brief = ("Interface              IP-Address      OK? Method Status                Protocol\n"
             "GigabitEthernet0/0     192.168.100.9   YES manual up                    up\n"
             "GigabitEthernet0/1     unassigned      YES unset  administratively down down\n")
    assert cisco.parse_interfaces(brief) == [
        InterfaceStatus("GigabitEthernet0/0", "192.168.100.9", True, True),
        InterfaceStatus("GigabitEthernet0/1", None, False, False)]
    arp = ("Protocol  Address          Age (min)  Hardware Addr   Type   Interface\n"
           "Internet  192.168.100.1           0   0050.5600.0001  ARPA   GigabitEthernet0/0\n")
    assert cisco.parse_arp(arp)[0]["mac"] == "00:50:56:00:00:01"
    assert cisco.parse_cpu("CPU utilization for five seconds: 3%/0%; one minute: 2%; five minutes: 1%") == 1.0


# ----------------------------------------- routing table, LLDP, memory (real output)
def test_mikrotik_routes_lldp_memory_and_full_ospf(mikrotik):
    routes = mikrotik.parse_routes(sample("mikrotik", "ip_route_terse"))
    assert routes[0] == RouteEntry("10.0.12.0/30", "connected", None, "ether2")
    assert routes[2] == RouteEntry("10.0.24.0/30", "ospf", "10.0.12.2", "ether2")
    assert [r.protocol for r in routes].count("ospf") == 2
    assert mikrotik.parse_lldp(sample("mikrotik", "ip_neighbor_terse"))[1] == LldpNeighbor(
        "ether2", "R2-MikroTik", "ether2", "MikroTik")
    assert mikrotik.parse_memory(sample("mikrotik", "system_resource")) == {"total_mb": 384.0, "used_percent": 54.5}
    assert mikrotik.parse_ospf_neighbors(sample("mikrotik", "ospf_neighbor_full")) == [
        OspfNeighbor("3.3.3.3", "10.0.13.2", "ether3", "Full"),
        OspfNeighbor("2.2.2.2", "10.0.12.2", "ether2", "Full"),
    ]


def test_vyos_routes_memory_and_full_ospf(vyos):
    routes = vyos.parse_routes(sample("vyos", "show_ip_route"))
    assert routes[0] == RouteEntry("10.0.12.0/30", "ospf", "10.0.13.1", "eth1")
    assert routes[2] == RouteEntry("10.0.13.2/32", "local", None, "eth1")
    assert vyos.parse_memory(sample("vyos", "show_system_memory")) == {"total_mb": 974.73, "used_percent": 55.8}
    assert [n.neighbor_id for n in vyos.parse_ospf_neighbors(sample("vyos", "show_ip_ospf_neighbor_full"))] == [
        "1.1.1.1", "4.4.4.4"]


def test_vyos_lldp_table():
    vyos = VyOSDevice("VY1", "192.0.2.21", CREDS)
    assert vyos.parse_lldp(sample("vyos", "show_lldp_neighbors_off")) == []
    synthetic = (
        "Capability Codes: R - Router, B - Bridge, W - Wlan r - Repeater, S - Station\n"
        "                  D - Docsis, T - Telephone, O - Other\n\n"
        "Device ID                 Local     Proto  Cap   Platform             Port ID\n"
        "---------                 -----     -----  ---   --------             -------\n"
        "R1-MikroTik               eth1      LLDP   BR    MikroTik             ether3\n")
    assert vyos.parse_lldp(synthetic) == [LldpNeighbor("eth1", "R1-MikroTik", "ether3", "MikroTik")]


def test_cisco_routes_lldp_memory():
    cisco = CiscoIOSDevice("R9", "192.0.2.9", CREDS)
    routes = cisco.parse_routes(
        "Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP\n"
        "Gateway of last resort is not set\n\n"
        "      10.0.0.0/8 is variably subnetted, 2 subnets, 2 masks\n"
        "C        10.0.12.0/30 is directly connected, GigabitEthernet0/1\n"
        "O        10.0.24.0/30 [110/2] via 10.0.12.2, 00:01:02, GigabitEthernet0/1\n")
    assert routes[1] == RouteEntry("10.0.24.0/30", "ospf", "10.0.12.2", "GigabitEthernet0/1")
    lldp = cisco.parse_lldp(
        "Device ID           Local Intf     Hold-time  Capability      Port ID\n"
        "R2                  Gi0/1          120        R               Gi0/1\n\nTotal entries displayed: 1\n")
    assert lldp == [LldpNeighbor("Gi0/1", "R2", "Gi0/1", None)]
    assert cisco.parse_memory("Processor Pool Total:  268435456 Used:  67108864 Free: 201326592") == {
        "total_mb": 256.0, "used_percent": 25.0}
