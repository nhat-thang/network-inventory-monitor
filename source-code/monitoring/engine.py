"""Run every anomaly rule on every device snapshot."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from core.models import Alert, DeviceFacts, TaskResult
from monitoring.rules import AnomalyRule

logger = logging.getLogger("netmon")


class MonitoringEngine:
    """Apply a list of rules and turn unreachable devices into alerts."""

    OFFLINE_RULE = "device_offline"

    def __init__(self, rules: List[AnomalyRule], snapshot_dir: Optional[Path] = None) -> None:
        self._rules = list(rules)
        self._snapshot_dir = Path(snapshot_dir) if snapshot_dir else None

    @property
    def rules(self) -> List[AnomalyRule]:
        """The rules applied by this engine."""
        return list(self._rules)

    def evaluate(
        self,
        facts: List[DeviceFacts],
        failures: List[TaskResult],
    ) -> List[Alert]:
        """Return all alerts, most severe first.

        - one ``critical`` alert per failed device (device offline);
        - every rule's alerts for each reachable device, comparing with the
          previous snapshot loaded by ``load_previous``.
        """
        alerts = [
            Alert(device=f.device, rule=self.OFFLINE_RULE, severity="critical",
                  message=f"Device unreachable: {f.error}")
            for f in failures
        ]
        previous = self.load_previous()
        for current in facts:
            before = previous.get(current.device)
            for rule in self._rules:
                try:
                    alerts.extend(rule.evaluate(current, before))
                except Exception as exc:  # noqa: BLE001 - a broken rule must not hide the others
                    logger.error("%s: rule %s failed: %s", current.device, rule.name, exc)
        alerts.sort(key=lambda a: (a.rank, a.device, a.rule))
        for alert in alerts:
            logger.log(logging.WARNING if alert.rank < 2 else logging.INFO,
                       "ALERT %s %s [%s] %s", alert.severity.upper(), alert.device, alert.rule, alert.message)
        return alerts

    def _snapshot_file(self, device: str) -> Path:
        assert self._snapshot_dir is not None
        return self._snapshot_dir / f"{device}.json"

    def load_previous(self) -> Dict[str, DeviceFacts]:
        """Load the last saved snapshot per device (empty dict if none)."""
        if self._snapshot_dir is None or not self._snapshot_dir.exists():
            return {}
        snapshots = {}
        for path in sorted(self._snapshot_dir.glob("*.json")):
            try:
                facts = DeviceFacts.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning("Ignoring unreadable snapshot %s: %s", path, exc)
                continue
            snapshots[facts.device] = facts
        return snapshots

    def save_snapshot(self, facts: List[DeviceFacts]) -> None:
        """Save the current snapshot for the next run (devices that failed keep their old one)."""
        if self._snapshot_dir is None:
            return
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        for item in facts:
            self._snapshot_file(item.device).write_text(
                json.dumps(item.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
            )
