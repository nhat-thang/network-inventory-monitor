"""Tests for the HTML dashboard (no network needed)."""

from core.models import Alert, DeviceFacts, InterfaceStatus, OspfNeighbor, TaskResult
from reporting import HtmlReport
from reporting.html_report import humanize_seconds


def _facts():
    return [
        DeviceFacts(device="R1", vendor="MikroTik RouterOS", hostname="R1-MikroTik", os_version="RouterOS 7.24.6",
                    uptime_seconds=3725, cpu_percent=12.0, serial="pNwYzAOYZKB",
                    interfaces=[InterfaceStatus("ether1", "192.168.100.11/24", True, True),
                                InterfaceStatus("ether2", "10.0.12.1/30", True, False)],
                    ospf_neighbors=[OspfNeighbor("3.3.3.3", "10.0.13.2", "ether3", "Full")]),
        DeviceFacts(device="VY1", vendor="VyOS", hostname="VY1-VyOS", cpu_percent=97.0,
                    arp_entries=[{"ip": "192.168.100.1", "mac": "00:50:56:c0:00:03", "interface": "eth0"}]),
    ]


ALERTS = [
    Alert("R1", "interface_down", "critical", "Interface ether2 went down"),
    Alert("VY1", "high_cpu", "critical", "CPU 97% (threshold 80%)"),
    Alert("VY2", "device_offline", "critical", "Device unreachable: DeviceTimeoutError: <script>x</script>"),
    Alert("R1", "config_changed", "info", "Running configuration changed since last scan"),
]
FAILURES = [TaskResult("VY2", False, error="DeviceTimeoutError: no response")]


def test_humanize_seconds():
    assert [humanize_seconds(s) for s in (None, 44, 66, 3725, 93784)] == ["—", "44s", "1m 6s", "1h 2m", "1d 2h 3m"]


def test_context_counts_and_device_status():
    ctx = HtmlReport().build_context(_facts(), FAILURES, ALERTS)
    assert (ctx["total"], ctx["online"], ctx["offline"]) == (3, 2, 1)
    assert (ctx["critical"], ctx["warning"], ctx["info"]) == (3, 0, 1)
    assert (ctx["interfaces_alerted"], ctx["interfaces_total"]) == (1, 2)
    assert [(d.get("name") or d["facts"].device, d["status"]) for d in ctx["devices"]] == [
        ("R1", "critical"), ("VY1", "critical"), ("VY2", "critical")]
    assert ctx["devices"][0]["interfaces_up"] == 1 and ctx["devices"][0]["ospf_full"] == 1


def test_render_writes_self_contained_escaped_html(tmp_path):
    out = HtmlReport().render(_facts(), FAILURES, ALERTS, tmp_path / "sub" / "report.html")
    html = out.read_text(encoding="utf-8")
    for text in ("R1-MikroTik", "1h 2m", "Interface ether2 went down", "Mất kết nối", "00:50:56:c0:00:03"):
        assert text in html
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html
    assert "http://" not in html and "https://" not in html  # no external resources


def test_render_without_alerts_shows_all_clear(tmp_path):
    html = HtmlReport().render(_facts()[:1], [], [], tmp_path / "r.html").read_text(encoding="utf-8")
    assert "Không phát hiện bất thường" in html
