"""Run ``get_facts()`` on many devices and export the results.

Vendor-specific parsing lives in each device class (``parse_*`` methods);
this module only orchestrates and exports.
"""

from pathlib import Path
from typing import List, Tuple

from core.connection_manager import ConnectionManager
from core.models import DeviceFacts, TaskResult
from devices.base import NetworkDevice


class FactsCollector:
    """Collect ``DeviceFacts`` from a list of devices."""

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager

    def collect(self, devices: List[NetworkDevice]) -> Tuple[List[DeviceFacts], List[TaskResult]]:
        """Return (facts of reachable devices, failed results)."""
        results = self._manager.run(devices, lambda dev: dev.get_facts())
        facts = [r.result for r in results if r.success]
        failures = [r for r in results if not r.success]
        return facts, failures

    # TODO (collectors): implement the exporters.
    @staticmethod
    def to_json(facts: List[DeviceFacts], path: Path) -> None:
        """Write facts to a JSON file."""
        raise NotImplementedError("FactsCollector.to_json")

    @staticmethod
    def to_csv(facts: List[DeviceFacts], path: Path) -> None:
        """Write one row per device to a CSV file."""
        raise NotImplementedError("FactsCollector.to_csv")
