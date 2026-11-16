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


# TODO (monitoring): implement the rules below.
class InterfaceDownRule(AnomalyRule):
    """Interface administratively up but operationally down."""

    @property
    def name(self) -> str:
        return "interface_down"

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        raise NotImplementedError("InterfaceDownRule.evaluate")


class HighCpuRule(AnomalyRule):
    """CPU usage above a threshold."""

    def __init__(self, threshold: float = 80.0) -> None:
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "high_cpu"

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        raise NotImplementedError("HighCpuRule.evaluate")


class OspfNeighborLostRule(AnomalyRule):
    """An OSPF neighbor present in the previous snapshot is gone."""

    @property
    def name(self) -> str:
        return "ospf_neighbor_lost"

    def evaluate(self, current: DeviceFacts, previous: Optional[DeviceFacts]) -> List[Alert]:
        raise NotImplementedError("OspfNeighborLostRule.evaluate")
