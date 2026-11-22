"""Application service: the one entry point used by every user interface.

Both the command line (``main.py``) and the web interface (``web/``) call this
class; neither of them talks to devices, files or rules directly. This keeps
the presentation layer separate from the business logic: the core still runs
on its own through the CLI.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from backup.backup_manager import BackupError, BackupManager
from collectors.facts_collector import FactsCollector
from core.connection_manager import ConnectionManager
from core.exceptions import ConfigPushError, InventoryError
from core.models import Alert, DeviceFacts, TaskResult
from devices.base import NetworkDevice
from inventory.inventory import Inventory
from monitoring import (
    ConfigChangedRule,
    HighCpuRule,
    HighMemoryRule,
    InterfaceDownRule,
    MonitoringEngine,
    OspfNeighborLostRule,
    RebootRule,
)
from provisioning.config_pusher import ConfigPusher
from reporting.excel_report import ExcelReport
from reporting.history import HistoryLog

logger = logging.getLogger("netmon")

ProgressCallback = Optional[Callable[[TaskResult], None]]


@dataclass
class ScanResult:
    """Everything one scan produced."""

    facts: List[DeviceFacts]
    failures: List[TaskResult]
    alerts: List[Alert]
    report_path: Path
    finished_at: datetime = field(default_factory=datetime.now)


class NetworkService:
    """Business operations on the device inventory."""

    def __init__(self, base_dir: Path, output_dir: Optional[Path] = None, workers: int = 8,
                 cpu_threshold: float = 80.0, memory_threshold: float = 90.0, source: str = "cli") -> None:
        self._base = Path(base_dir)
        self._out = Path(output_dir) if output_dir else self._base / "output"
        self._workers = workers
        self._cpu_threshold = cpu_threshold
        self._memory_threshold = memory_threshold
        self._source = source
        self._backups = BackupManager(self._out / "backups")
        self._history = HistoryLog(self._out / "history.jsonl")

    # ------------------------------------------------------------ paths
    @property
    def inventory_file(self) -> Path:
        return self._base / "inventory.yaml"

    @property
    def output_dir(self) -> Path:
        return self._out

    @property
    def reports_dir(self) -> Path:
        return self._out / "reports"

    @property
    def backups(self) -> BackupManager:
        return self._backups

    @property
    def history(self) -> HistoryLog:
        return self._history

    # -------------------------------------------------------- inventory
    def inventory(self) -> Inventory:
        """Fresh copy of the inventory from disk."""
        return Inventory(self.inventory_file).load()

    def select(self, names: Optional[List[str]] = None, group: Optional[str] = None,
               role: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Records chosen by name list and/or filters (all devices if nothing is given)."""
        records = self.inventory().filter(group=group, role=role, tag=tag)
        if names:
            wanted = set(names)
            unknown = wanted - {r["name"] for r in records}
            if unknown:
                raise InventoryError(f"Unknown or filtered-out device(s): {sorted(unknown)}")
            records = [r for r in records if r["name"] in wanted]
        return records

    def _build(self, records: List[Dict[str, Any]]) -> List[NetworkDevice]:
        return self.inventory().build_devices(records)

    # ------------------------------------------------------------- scan
    def rules(self) -> list:
        return [
            InterfaceDownRule(),
            HighCpuRule(self._cpu_threshold),
            HighMemoryRule(self._memory_threshold),
            OspfNeighborLostRule(),
            RebootRule(),
            ConfigChangedRule(),
        ]

    def scan(self, records: List[Dict[str, Any]], on_result: ProgressCallback = None) -> ScanResult:
        """Collect facts, detect anomalies, write JSON/CSV/Excel and the last-scan summary."""
        devices = self._build(records)
        manager = ConnectionManager(self._workers)
        results = manager.run(devices, lambda dev: dev.get_facts(), on_result=on_result)
        facts = sorted((r.result for r in results if r.success), key=lambda f: f.device)
        failures = sorted((r for r in results if not r.success), key=lambda r: r.device)
        engine = MonitoringEngine(self.rules(), snapshot_dir=self._out / "snapshots")
        alerts = engine.evaluate(facts, failures)
        engine.save_snapshot(facts)
        FactsCollector.to_json(facts, self._out / "facts.json")
        FactsCollector.to_csv(facts, self._out / "facts.csv")
        stamp = datetime.now()
        report = ExcelReport().render(
            facts, failures, alerts, self.reports_dir / f"report_{stamp:%Y%m%d-%H%M%S}.xlsx", stamp)
        self._save_last_scan(facts, failures, alerts, report, stamp)
        self._history.record("scan", [r["name"] for r in records], len(facts), len(failures),
                             f"{len(alerts)} cảnh báo, báo cáo {report.name}", self._source)
        return ScanResult(facts, failures, alerts, report, stamp)

    def _save_last_scan(self, facts, failures, alerts, report: Path, stamp: datetime) -> None:
        data = {
            "time": stamp.isoformat(timespec="seconds"),
            "online": [f.device for f in facts],
            "offline": [{"device": r.device, "error": r.error} for r in failures],
            "alerts": [{"device": a.device, "rule": a.rule, "severity": a.severity, "message": a.message,
                        "time": a.timestamp.isoformat(timespec="seconds")} for a in alerts],
            "report": report.name,
        }
        self._out.mkdir(parents=True, exist_ok=True)
        (self._out / "last_scan.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")

    def last_scan(self) -> Optional[Dict[str, Any]]:
        path = self._out / "last_scan.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def last_facts(self) -> Dict[str, DeviceFacts]:
        """Latest facts per device (from the monitoring snapshots)."""
        return MonitoringEngine([], snapshot_dir=self._out / "snapshots").load_previous()

    # ----------------------------------------------------------- backup
    def backup(self, records: List[Dict[str, Any]], on_result: ProgressCallback = None) -> List[TaskResult]:
        results = ConnectionManager(self._workers).run(self._build(records), self._backups.backup, on_result)
        ok = [r for r in results if r.success]
        self._history.record("backup", [r["name"] for r in records], len(ok), len(results) - len(ok),
                             ", ".join(Path(r.result).name for r in ok), self._source)
        return results

    def list_backups(self) -> Dict[str, List[Path]]:
        names = [r["name"] for r in self.inventory().records]
        return {name: self._backups.list_backups(name) for name in names}

    def backup_file(self, device: str, file_name: str) -> Path:
        """Resolve a backup file name safely (no path traversal)."""
        path = (self._backups.backup_dir / device / Path(file_name).name).resolve()
        if self._backups.backup_dir.resolve() not in path.parents or not path.is_file():
            raise BackupError(f"Backup not found: {device}/{file_name}")
        return path

    def diff(self, device: str, old: str, new: str) -> str:
        return self._backups.diff(self.backup_file(device, old), self.backup_file(device, new))

    def rollback(self, device: str, file_name: str) -> str:
        records = self.select([device])
        target = self.backup_file(device, file_name)
        dev = self._build(records)[0]
        try:
            with dev:
                output = self._backups.rollback(dev, target)
        except Exception as exc:
            self._history.record("rollback", [device], 0, 1, f"{file_name}: {exc}", self._source)
            raise
        self._history.record("rollback", [device], 1, 0, file_name, self._source)
        return output

    # ---------------------------------------------------- provisioning
    def templates(self) -> List[str]:
        """Template names available for every device type in the inventory (e.g. ospf, baseline)."""
        folder = self._base / "provisioning" / "templates"
        return sorted({p.name.split("_", 1)[0] for p in folder.glob("*.j2")})

    def _variables(self, template: str) -> Dict[str, Any]:
        path = self._base / "provisioning" / f"{template}_vars.yaml"
        if not path.exists():
            raise ConfigPushError(f"No variables file {path.name}")
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def render(self, template: str, records: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Config lines per device, without connecting (dry-run)."""
        variables = self._variables(template)
        pusher = ConfigPusher(self._base / "provisioning" / "templates", self._backups, template)
        rendered = {}
        for record, device in zip(records, self._build(records)):
            values = {**variables.get("all", {}), **variables.get(record["name"], {})}
            rendered[record["name"]] = pusher.render(device, record["device_type"], values)
        return rendered

    def deploy(self, template: str, records: List[Dict[str, Any]], dry_run: bool = False,
               on_result: ProgressCallback = None) -> List[TaskResult]:
        """Render and push a template to many devices in parallel (backup + auto-rollback per device)."""
        rendered = self.render(template, records)
        pusher = ConfigPusher(self._base / "provisioning" / "templates", self._backups, template)
        if dry_run:
            results = [TaskResult(name, True, "\n".join(lines)) for name, lines in rendered.items()]
            for r in results:
                if on_result:
                    on_result(r)
            self._history.record(f"deploy {template} (dry-run)", list(rendered), len(results), 0,
                                 source=self._source)
            return results
        def push(dev: NetworkDevice) -> str:
            lines = rendered[dev.name]
            pusher.deploy(dev, lines)  # backup first, rolls back by itself on error
            return f"{len(lines)} dòng đã áp:\n" + "\n".join(lines)

        results = ConnectionManager(self._workers).run(self._build(records), push, on_result)
        ok = sum(r.success for r in results)
        self._history.record(f"deploy {template}", list(rendered), ok, len(results) - ok, source=self._source)
        return results

    # ---------------------------------------------------------- reports
    def reports(self) -> List[Path]:
        """Excel reports, newest first."""
        if not self.reports_dir.exists():
            return []
        return sorted(self.reports_dir.glob("report_*.xlsx"), reverse=True)

    def report_file(self, name: str) -> Path:
        path = (self.reports_dir / Path(name).name).resolve()
        if self.reports_dir.resolve() not in path.parents or not path.is_file():
            raise BackupError(f"Report not found: {name}")
        return path

    def dashboard(self) -> Dict[str, Any]:
        """Numbers for the overview screen."""
        last = self.last_scan()
        backups = self.list_backups()
        return {
            "devices": len(self.inventory()),
            "last_scan": last,
            "online": len(last["online"]) if last else None,
            "offline": len(last["offline"]) if last else None,
            "alerts": last["alerts"] if last else [],
            "backup_count": sum(len(v) for v in backups.values()),
            "backup_devices": sum(1 for v in backups.values() if v),
            "history": self._history.entries(limit=15),
            "reports": len(self.reports()),
        }
