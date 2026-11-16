"""Save running configs with a timestamp, compare versions, roll back.

File layout: ``output/backups/<device>/<device>_<YYYYmmdd-HHMMSS>.cfg``
"""

from pathlib import Path
from typing import List

from devices.base import NetworkDevice


class BackupManager:
    """Manage configuration backups on disk."""

    def __init__(self, backup_dir: Path) -> None:
        self._backup_dir = Path(backup_dir)

    # TODO (backup): implement every method below.
    def backup(self, device: NetworkDevice) -> Path:
        """Save ``device.backup_config()`` to a new timestamped file and return its path."""
        raise NotImplementedError("BackupManager.backup")

    def list_backups(self, device_name: str) -> List[Path]:
        """Backups of one device, oldest first."""
        raise NotImplementedError("BackupManager.list_backups")

    def diff(self, old: Path, new: Path) -> str:
        """Unified diff between two backup files (``difflib``)."""
        raise NotImplementedError("BackupManager.diff")

    def rollback(self, device: NetworkDevice, backup_file: Path) -> str:
        """Push the configuration stored in ``backup_file`` back to the device."""
        raise NotImplementedError("BackupManager.rollback")
