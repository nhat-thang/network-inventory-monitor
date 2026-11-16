"""Factory that builds the right device subclass from an inventory record.

Subclasses register themselves with ``@DeviceFactory.register("<type>")``, so
adding a vendor never requires editing this file or any if/else chain.
"""

from typing import Any, Callable, Dict, List, Type

from core.credentials import Credentials
from core.exceptions import UnsupportedDeviceError
from devices.base import NetworkDevice


class DeviceFactory:
    """Registry of ``device_type`` -> ``NetworkDevice`` subclass."""

    _registry: Dict[str, Type[NetworkDevice]] = {}

    @classmethod
    def register(cls, device_type: str) -> Callable[[Type[NetworkDevice]], Type[NetworkDevice]]:
        """Class decorator that registers a subclass under ``device_type``."""

        def decorator(device_cls: Type[NetworkDevice]) -> Type[NetworkDevice]:
            cls._registry[device_type] = device_cls
            return device_cls

        return decorator

    @classmethod
    def supported_types(cls) -> List[str]:
        """All registered ``device_type`` values."""
        return sorted(cls._registry)

    @classmethod
    def create(cls, record: Dict[str, Any], credentials: Credentials) -> NetworkDevice:
        """Build a device object from one inventory record."""
        device_type = record.get("device_type", "")
        device_cls = cls._registry.get(device_type)
        if device_cls is None:
            raise UnsupportedDeviceError(
                f"Unsupported device_type {device_type!r}; supported: {cls.supported_types()}"
            )
        return device_cls(
            name=record["name"],
            host=record["host"],
            credentials=credentials,
            port=int(record.get("port", 22)),
            group=record.get("group"),
            role=record.get("role"),
            tags=record.get("tags", []),
        )
