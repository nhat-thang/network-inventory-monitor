"""Run ``get_facts()`` on many devices and export the results.

Vendor-specific parsing lives in each device class (``parse_*`` methods);
this module only orchestrates and exports.
"""

import csv
import json
from pathlib import Path
from typing import List, Tuple

from core.connection_manager import ConnectionManager
from core.models import DeviceFacts, TaskResult
from devices.base import NetworkDevice


class FactsCollector:
    """Collect ``DeviceFacts`` from a list of devices."""

    CSV_FIELDS = [
        "device", "vendor", "hostname", "os_version", "serial", "uptime_seconds", "cpu_percent",
        "interfaces_total", "interfaces_down", "ospf_neighbors", "arp_entries", "collected_at",
    ]

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager

    def collect(self, devices: List[NetworkDevice]) -> Tuple[List[DeviceFacts], List[TaskResult]]:
        """Return (facts of reachable devices, failed results), both sorted by device name."""
        results = self._manager.run(devices, lambda dev: dev.get_facts())
        facts = sorted((r.result for r in results if r.success), key=lambda f: f.device)
        failures = sorted((r for r in results if not r.success), key=lambda r: r.device)
        return facts, failures

    @staticmethod
    def to_json(facts: List[DeviceFacts], path: Path) -> None:
        """Write facts to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([f.to_dict() for f in facts], indent=2, ensure_ascii=False),
                        encoding="utf-8")

    @classmethod
    def to_csv(cls, facts: List[DeviceFacts], path: Path) -> None:
        """Write one row per device to a CSV file (UTF-8 with BOM so Excel opens it)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=cls.CSV_FIELDS)
            writer.writeheader()
            for f in facts:
                writer.writerow({
                    "device": f.device,
                    "vendor": f.vendor,
                    "hostname": f.hostname,
                    "os_version": f.os_version,
                    "serial": f.serial,
                    "uptime_seconds": f.uptime_seconds,
                    "cpu_percent": f.cpu_percent,
                    "interfaces_total": len(f.interfaces),
                    "interfaces_down": len(f.interfaces_down),
                    "ospf_neighbors": len(f.ospf_neighbors),
                    "arp_entries": len(f.arp_entries),
                    "collected_at": f.collected_at.isoformat(timespec="seconds"),
                })
