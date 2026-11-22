"""Abstract base class for every network device (abstraction + template method).

``NetworkDevice`` owns everything that is the same for all vendors: the SSH
session, error translation, the order in which facts are collected, backup and
the dry-run logic for pushing configuration. Each vendor subclass only says
*which* commands to send and *how* to read their output.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from core.credentials import Credentials
from core.exceptions import (
    ConfigPushError,
    DeviceAuthenticationError,
    DeviceConnectionError,
    DeviceTimeoutError,
)
from core.models import DeviceFacts, InterfaceStatus, OspfNeighbor


class NetworkDevice(ABC):
    """A network device reachable over SSH."""

    def __init__(
        self,
        name: str,
        host: str,
        credentials: Credentials,
        port: int = 22,
        group: Optional[str] = None,
        role: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        timeout: int = 10,
    ) -> None:
        self._name = name
        self._host = host
        self._port = port
        self._group = group
        self._role = role
        self._tags = list(tags or [])
        self._timeout = timeout
        self.__credentials = credentials
        self._connection: Any = None

    # ------------------------------------------------------------------ identity
    @property
    def name(self) -> str:
        """Device name as written in the inventory."""
        return self._name

    @property
    def host(self) -> str:
        """Management IP address."""
        return self._host

    @property
    def port(self) -> int:
        """SSH port."""
        return self._port

    @property
    def group(self) -> Optional[str]:
        """Inventory group, e.g. ``core``."""
        return self._group

    @property
    def role(self) -> Optional[str]:
        """Device role, e.g. ``router``."""
        return self._role

    @property
    def tags(self) -> List[str]:
        """Free-form labels used for filtering."""
        return list(self._tags)

    @property
    def is_connected(self) -> bool:
        """True while an SSH session is open."""
        return self._connection is not None

    # ------------------------------------------------------- vendor-specific API
    @property
    @abstractmethod
    def vendor(self) -> str:
        """Human-readable vendor/platform name."""

    @property
    @abstractmethod
    def netmiko_device_type(self) -> str:
        """``device_type`` string understood by Netmiko."""

    @property
    @abstractmethod
    def commands(self) -> Dict[str, str]:
        """Vendor CLI command for each fact.

        Required keys: ``version``, ``interfaces``, ``ospf_neighbors``,
        ``arp``, ``cpu``, ``running_config``.
        """

    @abstractmethod
    def parse_version(self, output: str) -> Dict[str, Any]:
        """Return ``hostname``, ``os_version``, ``serial``, ``uptime_seconds``."""

    @abstractmethod
    def parse_interfaces(self, output: str) -> List[InterfaceStatus]:
        """Return one ``InterfaceStatus`` per interface."""

    @abstractmethod
    def parse_ospf_neighbors(self, output: str) -> List[OspfNeighbor]:
        """Return the OSPF adjacencies."""

    @abstractmethod
    def parse_arp(self, output: str) -> List[Dict[str, Any]]:
        """Return ARP entries as dicts (``ip``, ``mac``, ``interface``)."""

    @abstractmethod
    def parse_cpu(self, output: str) -> Optional[float]:
        """Return CPU usage in percent."""

    @abstractmethod
    def _apply_config(self, lines: List[str]) -> str:
        """Send configuration lines and make them persistent (vendor-specific)."""

    # ---------------------------------------------------------------- session
    def connect(self) -> None:
        """Open the SSH session, translating library errors into our own."""
        if self.is_connected:
            return
        from netmiko import ConnectHandler
        from netmiko.exceptions import (
            NetmikoAuthenticationException,
            NetmikoTimeoutException,
        )

        params = {
            "device_type": self.netmiko_device_type,
            "host": self._host,
            "port": self._port,
            "username": self.__credentials.username,
            "password": self.__credentials.password,
            "timeout": self._timeout,
        }
        if self.__credentials.secret:
            params["secret"] = self.__credentials.secret
        try:
            self._connection = ConnectHandler(**params)
        except NetmikoAuthenticationException as exc:
            raise DeviceAuthenticationError(f"{self._name}: authentication failed") from exc
        except NetmikoTimeoutException as exc:
            raise DeviceTimeoutError(f"{self._name}: no response from {self._host}") from exc
        except Exception as exc:  # noqa: BLE001 - socket/paramiko errors
            raise DeviceConnectionError(f"{self._name}: {exc}") from exc

    def disconnect(self) -> None:
        """Close the SSH session if one is open."""
        if self._connection is not None:
            try:
                self._connection.disconnect()
            finally:
                self._connection = None

    def __enter__(self) -> "NetworkDevice":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()

    def send_command(self, command: str) -> str:
        """Run one show command and return its raw text output."""
        if not self.is_connected:
            raise DeviceConnectionError(f"{self._name}: not connected")
        return self._connection.send_command(command)

    # ------------------------------------------------------ template methods
    def get_facts(self) -> DeviceFacts:
        """Collect and normalize facts. Same steps for every vendor (template method)."""
        cmd = self.commands
        facts = DeviceFacts(device=self._name, vendor=self.vendor)
        version = self.collect_version()
        facts.hostname = version.get("hostname")
        facts.os_version = version.get("os_version")
        facts.serial = version.get("serial")
        facts.uptime_seconds = version.get("uptime_seconds")
        facts.interfaces = self.collect_interfaces()
        facts.ospf_neighbors = self.parse_ospf_neighbors(self.send_command(cmd["ospf_neighbors"]))
        facts.arp_entries = self.parse_arp(self.send_command(cmd["arp"]))
        facts.cpu_percent = self.parse_cpu(self.send_command(cmd["cpu"]))
        facts.config_hash = hashlib.sha256(self.backup_config().encode("utf-8")).hexdigest()
        return facts

    # ------------------------------------------------------------ hook methods
    # Most vendors answer each question with one command. A vendor that needs
    # several commands for one fact overrides the matching hook below.
    def collect_version(self) -> Dict[str, Any]:
        """Hook: run the version command(s) and return the parsed dict."""
        return self.parse_version(self.send_command(self.commands["version"]))

    def collect_interfaces(self) -> List[InterfaceStatus]:
        """Hook: run the interface command(s) and return the parsed list."""
        return self.parse_interfaces(self.send_command(self.commands["interfaces"]))

    def backup_config(self) -> str:
        """Return the current running configuration as text."""
        return self.send_command(self.commands["running_config"])

    def push_config(self, lines: List[str], dry_run: bool = False) -> str:
        """Apply configuration lines; with ``dry_run`` only return what would be sent."""
        if dry_run:
            return "\n".join(lines)
        if not self.is_connected:
            raise DeviceConnectionError(f"{self._name}: not connected")
        try:
            return self._apply_config(lines)
        except Exception as exc:  # noqa: BLE001
            raise ConfigPushError(f"{self._name}: {exc}") from exc

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self._name!r}, host={self._host!r})"
