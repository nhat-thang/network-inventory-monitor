"""Tests for anomaly rules, the monitoring engine and the exporters (no network needed)."""

import csv
import json

import pytest

from collectors import FactsCollector
from core.models import Alert, DeviceFacts, InterfaceStatus, OspfNeighbor, TaskResult
from monitoring import (
    ConfigChangedRule,
    HighCpuRule,
    InterfaceDownRule,
    MonitoringEngine,
    OspfNeighborLostRule,
    RebootRule,
)


def facts(device="R1", cpu=5.0, uptime=1000, eth2_up=True, ospf_state="Full", config="aaa"):
    return DeviceFacts(
        device=device, vendor="MikroTik RouterOS", hostname=f"{device}-MikroTik",
        os_version="RouterOS 7.24.6", uptime_seconds=uptime, cpu_percent=cpu, config_hash=config,
        interfaces=[
            InterfaceStatus("ether1", "192.168.100.11/24", True, True),
            InterfaceStatus("ether2", "10.0.12.1/30", True, eth2_up),
            InterfaceStatus("ether7", None, True, False),   # unused port: no alert
            InterfaceStatus("ether8", None, False, False),  # disabled: never an alert
        ],
        ospf_neighbors=[OspfNeighbor("2.2.2.2", "10.0.12.2", "ether2", ospf_state)] if ospf_state else [],
    )


def messages(alerts):
    return [(a.severity, a.message) for a in alerts]


def test_interface_down_warning_then_critical_when_it_was_up():
    rule = InterfaceDownRule()
    assert messages(rule.evaluate(facts(eth2_up=False), None)) == [
        ("warning", "Interface ether2 (10.0.12.1/30) is enabled but down")]
    assert messages(rule.evaluate(facts(eth2_up=False), facts())) == [
        ("critical", "Interface ether2 went down")]
    assert rule.evaluate(facts(), facts()) == []


@pytest.mark.parametrize("cpu, expected", [(None, []), (79.9, []), (80, ["warning"]), (97, ["critical"])])
def test_high_cpu(cpu, expected):
    assert [a.severity for a in HighCpuRule(80).evaluate(facts(cpu=cpu), None)] == expected


def test_high_cpu_rejects_bad_threshold():
    with pytest.raises(ValueError):
        HighCpuRule(0)


def test_ospf_neighbor_lost_only_compared_to_previous():
    rule = OspfNeighborLostRule()
    assert rule.evaluate(facts(ospf_state=None), None) == []
    assert messages(rule.evaluate(facts(ospf_state=None), facts())) == [
        ("critical", "OSPF neighbor 2.2.2.2 lost")]
    assert len(rule.evaluate(facts(ospf_state="Init"), facts())) == 1
    assert rule.evaluate(facts(), facts()) == []


def test_reboot_and_config_change():
    assert [a.rule for a in RebootRule().evaluate(facts(uptime=30), facts(uptime=5000))] == ["reboot"]
    assert RebootRule().evaluate(facts(uptime=6000), facts(uptime=5000)) == []
    assert [a.severity for a in ConfigChangedRule().evaluate(facts(config="bbb"), facts())] == ["info"]
    assert ConfigChangedRule().evaluate(facts(), facts()) == []


class _BrokenRule(InterfaceDownRule):
    @property
    def name(self):
        return "broken"

    def evaluate(self, current, previous):
        raise RuntimeError("boom")


def test_engine_offline_alerts_snapshots_and_ordering(tmp_path):
    engine = MonitoringEngine([InterfaceDownRule(), OspfNeighborLostRule(), _BrokenRule()],
                              snapshot_dir=tmp_path / "snap")
    first = engine.evaluate([facts()], [TaskResult("VY2", False, error="DeviceTimeoutError: x")])
    assert messages(first) == [("critical", "Device unreachable: DeviceTimeoutError: x")]
    engine.save_snapshot([facts()])
    assert set(engine.load_previous()) == {"R1"}

    second = engine.evaluate([facts(eth2_up=False, ospf_state=None)], [])
    assert [a.severity for a in second] == ["critical", "critical"]
    assert {a.rule for a in second} == {"interface_down", "ospf_neighbor_lost"}


def test_engine_ignores_corrupt_snapshot(tmp_path):
    (tmp_path / "R1.json").write_text("{not json", encoding="utf-8")
    assert MonitoringEngine([], snapshot_dir=tmp_path).load_previous() == {}


def test_alert_rank_orders_by_severity():
    alerts = [Alert("A", "r", s, "m") for s in ("info", "critical", "warning")]
    assert [a.severity for a in sorted(alerts, key=lambda a: a.rank)] == ["critical", "warning", "info"]


def test_facts_round_trip_and_exports(tmp_path):
    original = facts()
    again = DeviceFacts.from_dict(json.loads(json.dumps(original.to_dict())))
    assert again.interfaces == original.interfaces and again.ospf_neighbors == original.ospf_neighbors

    FactsCollector.to_json([original], tmp_path / "out" / "facts.json")
    assert json.loads((tmp_path / "out" / "facts.json").read_text(encoding="utf-8"))[0]["device"] == "R1"

    FactsCollector.to_csv([original], tmp_path / "facts.csv")
    with (tmp_path / "facts.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))
    assert (row["device"], row["interfaces_total"], row["interfaces_down"]) == ("R1", "4", "1")
