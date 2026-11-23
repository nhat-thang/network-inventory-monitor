"""Anomaly detection rules (Strategy pattern) and the engine that runs them."""

from monitoring.engine import MonitoringEngine
from monitoring.rules import (
    AnomalyRule,
    ConfigChangedRule,
    HighCpuRule,
    InterfaceDownRule,
    OspfNeighborLostRule,
    RebootRule,
)

__all__ = [
    "MonitoringEngine",
    "AnomalyRule",
    "ConfigChangedRule",
    "HighCpuRule",
    "InterfaceDownRule",
    "OspfNeighborLostRule",
    "RebootRule",
]
