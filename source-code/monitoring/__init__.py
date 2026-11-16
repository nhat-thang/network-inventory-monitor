"""Anomaly detection rules (Strategy pattern) and the engine that runs them."""

from monitoring.engine import MonitoringEngine
from monitoring.rules import (
    AnomalyRule,
    HighCpuRule,
    InterfaceDownRule,
    OspfNeighborLostRule,
)

__all__ = [
    "MonitoringEngine",
    "AnomalyRule",
    "HighCpuRule",
    "InterfaceDownRule",
    "OspfNeighborLostRule",
]
