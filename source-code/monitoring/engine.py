"""Run every anomaly rule on every device snapshot."""

from pathlib import Path
from typing import Dict, List, Optional

from core.models import Alert, DeviceFacts, TaskResult
from monitoring.rules import AnomalyRule


class MonitoringEngine:
    """Apply a list of rules and turn unreachable devices into alerts."""

    def __init__(self, rules: List[AnomalyRule], snapshot_dir: Optional[Path] = None) -> None:
        self._rules = list(rules)
        self._snapshot_dir = snapshot_dir

    # TODO (monitoring): implement.
    def evaluate(
        self,
        facts: List[DeviceFacts],
        failures: List[TaskResult],
    ) -> List[Alert]:
        """Return all alerts.

        - one ``critical`` alert per failed device (device offline);
        - every rule's alerts for each reachable device, comparing with the
          previous snapshot loaded by ``load_previous``.
        """
        raise NotImplementedError("MonitoringEngine.evaluate")

    def load_previous(self) -> Dict[str, DeviceFacts]:
        """Load the last saved snapshot per device (empty dict if none)."""
        raise NotImplementedError("MonitoringEngine.load_previous")

    def save_snapshot(self, facts: List[DeviceFacts]) -> None:
        """Save the current snapshot for the next run."""
        raise NotImplementedError("MonitoringEngine.save_snapshot")
