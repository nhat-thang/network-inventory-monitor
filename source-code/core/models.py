"""Shared data contracts.

Every module exchanges data through these dataclasses, so team members can
work in parallel: collectors produce ``DeviceFacts``, monitoring rules read
them and produce ``Alert`` objects, reporting renders both.
Change these only after agreeing with the whole team.
"""

from dataclasses import asdict, dataclass, field
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
class RouteEntry:
    """One route in the routing table."""

    prefix: str
    protocol: str  # connected | local | static | ospf | bgp | rip | kernel | dhcp | other
    next_hop: Optional[str]
    interface: Optional[str]


@dataclass
class LldpNeighbor:
    """A directly connected neighbor discovered by LLDP (or CDP/MNDP)."""

    local_interface: str
    neighbor: str
    neighbor_port: Optional[str]
    platform: Optional[str]


@dataclass
class ComplianceResult:
    """Outcome of one compliance check on one device."""

    check: str
    description: str
    passed: bool
    detail: str = ""


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
    memory_total_mb: Optional[float] = None
    memory_percent: Optional[float] = None
    interfaces: List[InterfaceStatus] = field(default_factory=list)
    ospf_neighbors: List[OspfNeighbor] = field(default_factory=list)
    routes: List[RouteEntry] = field(default_factory=list)
    lldp_neighbors: List[LldpNeighbor] = field(default_factory=list)
    arp_entries: List[Dict[str, Any]] = field(default_factory=list)
    config_hash: Optional[str] = None
    compliance: List[ComplianceResult] = field(default_factory=list)
    collected_at: datetime = field(default_factory=datetime.now)

    @property
    def interfaces_down(self) -> List[InterfaceStatus]:
        """Interfaces enabled by the admin but without link."""
        return [i for i in self.interfaces if i.admin_up and not i.oper_up]

    @property
    def compliance_percent(self) -> Optional[float]:
        """Share of compliance checks passed (None if none were run)."""
        if not self.compliance:
            return None
        return round(100 * sum(c.passed for c in self.compliance) / len(self.compliance), 1)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly dict (datetime as ISO string)."""
        data = asdict(self)
        data["collected_at"] = self.collected_at.isoformat(timespec="seconds")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceFacts":
        """Inverse of ``to_dict`` (used to reload saved snapshots)."""
        data = dict(data)
        data["interfaces"] = [InterfaceStatus(**i) for i in data.get("interfaces", [])]
        data["ospf_neighbors"] = [OspfNeighbor(**n) for n in data.get("ospf_neighbors", [])]
        data["routes"] = [RouteEntry(**r) for r in data.get("routes", [])]
        data["lldp_neighbors"] = [LldpNeighbor(**n) for n in data.get("lldp_neighbors", [])]
        data["compliance"] = [ComplianceResult(**c) for c in data.get("compliance", [])]
        if isinstance(data.get("collected_at"), str):
            data["collected_at"] = datetime.fromisoformat(data["collected_at"])
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Alert:
    """An anomaly found by a monitoring rule."""

    device: str
    rule: str
    severity: str  # "info" | "warning" | "critical"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)

    SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

    @property
    def rank(self) -> int:
        """0 = most severe; used to sort alerts."""
        return self.SEVERITY_ORDER.get(self.severity, 3)


@dataclass
class TaskResult:
    """Outcome of running one task on one device."""

    device: str
    success: bool
    result: Any = None
    error: Optional[str] = None
