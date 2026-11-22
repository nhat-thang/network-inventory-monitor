"""End-to-end tests of the service layer, the Markdown report and the web UI with simulated devices."""

import shutil
from pathlib import Path

import pytest

from core.scheduler import PeriodicRunner
from reporting.history import HistoryLog
from services import NetworkService
from tests.fakes import FakeMikroTik, FakeVyOS, use_fake_devices

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def base(tmp_path, monkeypatch):
    """A copy of the project inputs (inventory, templates, vars) in a temp folder."""
    use_fake_devices(monkeypatch)
    shutil.copy(ROOT / "inventory.yaml", tmp_path / "inventory.yaml")
    shutil.copytree(ROOT / "provisioning", tmp_path / "provisioning",
                    ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    return tmp_path


@pytest.fixture
def service(base):
    return NetworkService(base, base / "output", workers=4)


def test_scan_writes_markdown_json_snapshot_and_history(service):
    seen = []
    result = service.scan(service.select(), on_result=lambda r: seen.append(r.device))
    assert sorted(seen) == ["R1", "R2", "VY1", "VY2"]
    assert [f.device for f in result.facts] == ["R1", "R2", "VY1", "VY2"] and not result.failures
    r1 = result.facts[0]
    assert len(r1.routes) == 5 and len(r1.lldp_neighbors) == 2 and r1.memory_percent == 54.5

    text = result.report_path.read_text(encoding="utf-8")
    assert result.report_path.suffix == ".md" and text.startswith("# Báo cáo kiểm kê")
    assert "| Trực tuyến | 4 |" in text and text.count("### ") == 4
    assert "| 10.0.24.0/30 | ospf | 10.0.12.2 | ether2 |" in text
    assert "| ether1 | R2-MikroTik | ether1 | MikroTik |" in text
    assert (service.output_dir / "facts.json").exists() and service.last_scan()["online"] == ["R1", "R2", "VY1", "VY2"]
    assert service.history.entries()[0]["action"] == "scan"


def test_scan_reports_offline_device(service):
    FakeVyOS.down = {"VY2"}
    result = service.scan(service.select())
    assert [f.device for f in result.failures] == ["VY2"]
    assert any(a.rule == "device_offline" and a.device == "VY2" for a in result.alerts)
    text = result.report_path.read_text(encoding="utf-8")
    assert "| VY2 | **Mất kết nối** |" in text and "## 5. Thiết bị không kết nối được" in text


def test_backup_deploy_and_select(service):
    results = service.backup(service.select(["R1", "VY1"]))
    assert all(r.success for r in results) and service.dashboard()["backup_count"] == 2

    dry = service.deploy("baseline", service.select(tag="vyos"), dry_run=True)
    assert [r.device for r in dry] == ["VY1", "VY2"] and "set service lldp interface all" in dry[0].result
    assert FakeVyOS.pushed == {}

    real = service.deploy("ospf", service.select(["R1"]))
    assert real[0].success and len(FakeMikroTik.pushed["R1"]) == 6
    assert service.templates() == ["baseline", "ospf"]

    with pytest.raises(Exception, match="Unknown"):
        service.select(["NOPE"])


def test_backup_file_rejects_path_traversal(service):
    service.backup(service.select(["R1"]))
    name = service.backups.list_backups("R1")[0].name
    assert service.backup_file("R1", name).exists()
    with pytest.raises(Exception):
        service.backup_file("R1", "../../inventory.yaml")


def test_periodic_runner_and_history(tmp_path):
    calls = []
    runner = PeriodicRunner(lambda: calls.append(1), interval_minutes=0.0001, times=3)
    runner.run()
    assert len(calls) == 3 == runner.runs
    with pytest.raises(ValueError):
        PeriodicRunner(lambda: None, 0)
    log = HistoryLog(tmp_path / "h.jsonl")
    log.record("scan", ["R1"], 1, 0)
    log.record("backup", ["R1"], 0, 1, "timeout")
    assert [e["action"] for e in log.entries()] == ["backup", "scan"]


# ------------------------------------------------------------------- web
@pytest.fixture
def client(base):
    from web.app import create_app

    app = create_app(base, base / "output")
    app.config["TESTING"] = True
    return app.test_client()


def _run_task(client, data):
    resp = client.post("/tasks", data=data)
    assert resp.status_code == 302
    task_url = resp.headers["Location"]
    events = client.get(task_url + "/events").get_data(as_text=True)
    return client.get(task_url).get_data(as_text=True), events


def test_web_pages_and_live_scan(client):
    for url in ["/", "/devices", "/backups", "/reports", "/history", "/devices/R1"]:
        assert client.get(url).status_code == 200, url
    page, events = _run_task(client, {"action": "scan", "device": ["R1", "VY1"]})
    assert "Tác vụ #1" in page
    assert events.count('"type": "device"') == 2 and '"type": "done"' in events and "report_" in events
    assert "R1-MikroTik" in client.get("/devices/R1").get_data(as_text=True)
    assert "TRỰC TUYẾN" in client.get("/devices").get_data(as_text=True)
    report = client.get("/reports").get_data(as_text=True)
    name = "report_" + report.split("report_")[1].split(".md")[0] + ".md"
    assert "# Báo cáo kiểm kê" in client.get(f"/reports/{name}").get_data(as_text=True)
    download = client.get(f"/reports/{name}?download=1")
    assert download.status_code == 200 and "attachment" in download.headers["Content-Disposition"]


def test_web_backup_view_diff_and_deploy(client):
    _run_task(client, {"action": "backup", "device": ["VY1"]})
    _run_task(client, {"action": "backup", "device": ["VY1"]})
    page = client.get("/backups").get_data(as_text=True)
    files = sorted(set(part.split('"')[0] for part in page.split('value="')[1:] if part.startswith("VY1_")))
    assert len(files) == 2
    assert "set service ssh" in client.get(f"/backups/VY1/{files[0]}").get_data(as_text=True)
    assert client.get(f"/backups/VY1/{files[0]}?download=1").status_code == 200
    assert "giống nhau" in client.get(f"/backups/VY1/diff?old={files[0]}&new={files[1]}").get_data(as_text=True)
    _, events = _run_task(client, {"action": "deploy", "template": "baseline", "dry_run": "1", "device": ["VY1"]})
    assert "set service lldp interface all" in events
    assert "deploy baseline (dry-run)" in client.get("/history").get_data(as_text=True)


def test_web_requires_a_device(client):
    resp = client.post("/tasks", data={"action": "scan"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/devices")


def test_markdown_table_escapes_pipes_and_empty_values():
    from reporting.markdown_report import md_table

    text = md_table(["A", "B"], [["x|y", None], ["multi\nline", 3.6]], right=[1])
    assert "| x\\|y | - |" in text and "| multi line | 4 |" in text and "| --- | ---: |" in text
    assert md_table(["A"], []) == "_Không có dữ liệu._\n"
