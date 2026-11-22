"""Anomaly rules (Strategy pattern).

Each rule is one class with one ``evaluate`` method. Adding a rule = adding a
class and passing it to ``MonitoringEngine``; no existing code changes.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from core.models import Alert, DeviceFacts


class AnomalyRule(ABC):
    """Base class for every anomaly rule."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short rule identifier shown in reports."""

    @abstractmethod
    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        """Return alerts for ``current`` (``previous`` = last snapshot, may be None)."""

    def _alert(self, facts: DeviceFacts, severity: str, message: str) -> Alert:
        return Alert(device=facts.device, rule=self.name, severity=severity, message=message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class InterfaceDownRule(AnomalyRule):
    """Interface administratively up but operationally down.

    ``critical`` if the interface was up in the previous scan (it just went
    down), ``warning`` otherwise.
    """

    @property
    def name(self) -> str:
        return "interface_down"

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        was_up = set()
        if previous is not None:
            was_up = {i.name for i in previous.interfaces if i.oper_up}
        alerts = []
        for intf in current.interfaces_down:
            if intf.name in was_up:
                alerts.append(self._alert(current, "critical", f"Interface {intf.name} went down"))
            else:
                alerts.append(self._alert(current, "warning", f"Interface {intf.name} is enabled but down"))
        return alerts


class HighCpuRule(AnomalyRule):
    """CPU usage above a threshold (``critical`` from 95 %)."""

    CRITICAL = 95.0

    def __init__(self, threshold: float = 80.0) -> None:
        if not 0 < threshold <= 100:
            raise ValueError("threshold must be in (0, 100]")
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "high_cpu"

    @property
    def threshold(self) -> float:
        """Warning threshold in percent."""
        return self._threshold

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        cpu = current.cpu_percent
        if cpu is None or cpu < self._threshold:
            return []
        severity = "critical" if cpu >= self.CRITICAL else "warning"
        return [self._alert(current, severity, f"CPU {cpu:.0f}% (threshold {self._threshold:.0f}%)")]

    def __repr__(self) -> str:
        return f"HighCpuRule(threshold={self._threshold})"


class OspfNeighborLostRule(AnomalyRule):
    """An OSPF neighbor that was Full in the previous snapshot is gone or not Full."""

    @property
    def name(self) -> str:
        return "ospf_neighbor_lost"

    @staticmethod
    def _full(facts: DeviceFacts) -> set:
        return {n.neighbor_id for n in facts.ospf_neighbors if n.state.lower().startswith("full")}

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        if previous is None:
            return []
        lost = sorted(self._full(previous) - self._full(current))
        return [self._alert(current, "critical", f"OSPF neighbor {rid} lost") for rid in lost]


class RebootRule(AnomalyRule):
    """Uptime is lower than in the previous scan: the device restarted."""

    @property
    def name(self) -> str:
        return "reboot"

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        if previous is None or current.uptime_seconds is None or previous.uptime_seconds is None:
            return []
        if current.uptime_seconds < previous.uptime_seconds:
            return [self._alert(current, "warning",
                                f"Device restarted (uptime {current.uptime_seconds}s)")]
        return []


class ConfigChangedRule(AnomalyRule):
    """Running configuration differs from the previous scan."""

    @property
    def name(self) -> str:
        return "config_changed"

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        if previous is None or not current.config_hash or not previous.config_hash:
            return []
        if current.config_hash != previous.config_hash:
            return [self._alert(current, "info", "Running configuration changed since last scan")]
        return []
