"""Shared data contracts.

Every module exchanges data through these dataclasses, so team members can
work in parallel: collectors produce ``DeviceFacts``, monitoring rules read
them and produce ``Alert`` objects, reporting renders both.
Change these only after agreeing with the whole team.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class InterfaceStatus:
    """State of one interface on a device."""

    name: str
    ip_address: Optional[str]
    admin_up: bool
    oper_up: bool


@dataclass
class OspfNeighbor:
    """One OSPF adjacency seen by a device."""

    neighbor_id: str
    address: str
    interface: str
    state: str


@dataclass
class DeviceFacts:
    """Normalized snapshot of a device, identical in shape for every vendor."""

    device: str
    vendor: str
    hostname: Optional[str] = None
    os_version: Optional[str] = None
    serial: Optional[str] = None
    uptime_seconds: Optional[int] = None
    cpu_percent: Optional[float] = None
    interfaces: List[InterfaceStatus] = field(default_factory=list)
    ospf_neighbors: List[OspfNeighbor] = field(default_factory=list)
    arp_entries: List[Dict[str, Any]] = field(default_factory=list)
    config_hash: Optional[str] = None
    collected_at: datetime = field(default_factory=datetime.now)


@dataclass
class Alert:
    """An anomaly found by a monitoring rule."""

    device: str
    rule: str
    severity: str  # "info" | "warning" | "critical"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TaskResult:
    """Outcome of running one task on one device."""

    device: str
    success: bool
    result: Any = None
    error: Optional[str] = None
