"""Inventory backed by a YAML file (see ``inventory.yaml``).

Each record is a dict with: ``name``, ``host``, ``port``, ``device_type``,
``group``, ``role``, ``tags`` and optionally ``credentials`` (an env prefix).
"""

import ipaddress
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from core.credentials import Credentials
from core.exceptions import InventoryError
import devices  # noqa: F401  (registers every vendor class with the factory)
from devices.base import NetworkDevice
from devices.factory import DeviceFactory


class Inventory:
    """Collection of device records loaded from YAML."""

    REQUIRED_FIELDS = ("name", "host", "device_type")
    ALLOWED_FIELDS = REQUIRED_FIELDS + ("port", "group", "role", "tags", "credentials")

    def __init__(self, path: Union[str, Path]) -> None:
        self._path = Path(path)
        self._records: List[Dict[str, Any]] = []

    @property
    def path(self) -> Path:
        """Location of the YAML file."""
        return self._path

    @property
    def records(self) -> List[Dict[str, Any]]:
        """A copy of all device records."""
        return [dict(r) for r in self._records]

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, name: object) -> bool:
        return any(r["name"] == name for r in self._records)

    # ------------------------------------------------------------- file I/O
    def load(self) -> "Inventory":
        """Read and validate the YAML file; return ``self`` for chaining."""
        if not self._path.exists():
            raise InventoryError(f"Inventory file not found: {self._path}")
        try:
            data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise InventoryError(f"Invalid YAML in {self._path}: {exc}") from exc
        devices = data.get("devices", []) if isinstance(data, dict) else None
        if not isinstance(devices, list):
            raise InventoryError(f"{self._path}: top-level key 'devices' must be a list")
        self._records = []
        for record in devices:
            self.add(record)
        return self

    def save(self) -> None:
        """Write the current records back to the YAML file."""
        header = (
            "# Device inventory for the GNS3 lab (see lab/ip-plan.md).\n"
            "# Credentials are NOT stored here; they come from .env.\n"
        )
        body = yaml.safe_dump(
            {"devices": self._records}, sort_keys=False, allow_unicode=True, default_flow_style=None
        )
        self._path.write_text(header + body, encoding="utf-8")

    # --------------------------------------------------------------- queries
    def get(self, name: str) -> Dict[str, Any]:
        """Return a copy of one record by name."""
        return dict(self._find(name))

    def filter(
        self,
        group: Optional[str] = None,
        role: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return records matching every given criterion."""
        result = []
        for record in self._records:
            if group is not None and record.get("group") != group:
                continue
            if role is not None and record.get("role") != role:
                continue
            if tag is not None and tag not in record.get("tags", []):
                continue
            result.append(dict(record))
        return result

    # ------------------------------------------------------------ mutations
    def add(self, record: Dict[str, Any]) -> None:
        """Add a device; reject duplicates and missing required fields."""
        clean = self._validate(record)
        if clean["name"] in self:
            raise InventoryError(f"Device {clean['name']!r} already exists")
        self._records.append(clean)

    def update(self, name: str, **changes: Any) -> None:
        """Change fields of an existing device."""
        current = self._find(name)
        merged = {**current, **{k: v for k, v in changes.items() if v is not None}}
        clean = self._validate(merged)
        if clean["name"] != name and clean["name"] in self:
            raise InventoryError(f"Device {clean['name']!r} already exists")
        current.clear()
        current.update(clean)

    def remove(self, name: str) -> None:
        """Delete a device by name."""
        self._records.remove(self._find(name))

    # --------------------------------------------------------------- devices
    def build_devices(self, records: Optional[List[Dict[str, Any]]] = None) -> List[NetworkDevice]:
        """Turn records into device objects via ``DeviceFactory``.

        Credentials come from ``Credentials.from_env(record.get("credentials", "NET"))``.
        """
        records = self._records if records is None else records
        cache: Dict[str, Credentials] = {}
        devices = []
        for record in records:
            prefix = record.get("credentials", "NET")
            if prefix not in cache:
                cache[prefix] = Credentials.from_env(prefix)
            devices.append(DeviceFactory.create(record, cache[prefix]))
        return devices

    # -------------------------------------------------------------- helpers
    def _find(self, name: str) -> Dict[str, Any]:
        for record in self._records:
            if record["name"] == name:
                return record
        raise InventoryError(f"Unknown device: {name!r}")

    @classmethod
    def _validate(cls, record: Any) -> Dict[str, Any]:
        if not isinstance(record, dict):
            raise InventoryError(f"Device record must be a mapping, got {type(record).__name__}")
        missing = [f for f in cls.REQUIRED_FIELDS if not record.get(f)]
        if missing:
            raise InventoryError(f"Device {record.get('name', '?')!r}: missing field(s) {missing}")
        unknown = set(record) - set(cls.ALLOWED_FIELDS)
        if unknown:
            raise InventoryError(f"Device {record['name']!r}: unknown field(s) {sorted(unknown)}")
        try:
            ipaddress.ip_address(str(record["host"]))
        except ValueError as exc:
            raise InventoryError(f"Device {record['name']!r}: invalid host {record['host']!r}") from exc
        if record["device_type"] not in DeviceFactory.supported_types():
            raise InventoryError(
                f"Device {record['name']!r}: unsupported device_type {record['device_type']!r}; "
                f"supported: {DeviceFactory.supported_types()}"
            )
        port = int(record.get("port", 22))
        if not 1 <= port <= 65535:
            raise InventoryError(f"Device {record['name']!r}: invalid port {port}")
        tags = record.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        clean: Dict[str, Any] = {
            "name": str(record["name"]),
            "host": str(record["host"]),
            "port": port,
            "device_type": record["device_type"],
        }
        for key in ("group", "role", "credentials"):
            if record.get(key):
                clean[key] = str(record[key])
        clean["tags"] = list(tags)
        return clean
