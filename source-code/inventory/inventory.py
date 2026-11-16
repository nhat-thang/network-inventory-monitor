"""Inventory backed by a YAML file (see ``inventory.yaml``).

Each record is a dict with: ``name``, ``host``, ``port``, ``device_type``,
``group``, ``role``, ``tags`` and optionally ``credentials`` (an env prefix).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from devices.base import NetworkDevice


class Inventory:
    """Collection of device records loaded from YAML."""

    REQUIRED_FIELDS = ("name", "host", "device_type")

    def __init__(self, path: Union[str, Path]) -> None:
        self._path = Path(path)
        self._records: List[Dict[str, Any]] = []

    @property
    def records(self) -> List[Dict[str, Any]]:
        """A copy of all device records."""
        return [dict(r) for r in self._records]

    # TODO (inventory): implement every method below.
    def load(self) -> "Inventory":
        """Read and validate the YAML file; return ``self`` for chaining."""
        raise NotImplementedError("Inventory.load")

    def save(self) -> None:
        """Write the current records back to the YAML file."""
        raise NotImplementedError("Inventory.save")

    def filter(
        self,
        group: Optional[str] = None,
        role: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return records matching every given criterion."""
        raise NotImplementedError("Inventory.filter")

    def add(self, record: Dict[str, Any]) -> None:
        """Add a device; reject duplicates and missing required fields."""
        raise NotImplementedError("Inventory.add")

    def update(self, name: str, **changes: Any) -> None:
        """Change fields of an existing device."""
        raise NotImplementedError("Inventory.update")

    def remove(self, name: str) -> None:
        """Delete a device by name."""
        raise NotImplementedError("Inventory.remove")

    def build_devices(self, records: Optional[List[Dict[str, Any]]] = None) -> List[NetworkDevice]:
        """Turn records into device objects via ``DeviceFactory``.

        Credentials come from ``Credentials.from_env(record.get("credentials", "NET"))``.
        """
        raise NotImplementedError("Inventory.build_devices")
