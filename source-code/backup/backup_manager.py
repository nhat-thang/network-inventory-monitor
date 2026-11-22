"""Save running configs with a timestamp, compare versions, roll back.

File layout: ``output/backups/<device>/<device>_<YYYYmmdd-HHMMSS>.cfg``
"""

import difflib
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from core.exceptions import ConfigPushError, NetworkAutomationError
from devices.base import NetworkDevice

logger = logging.getLogger("netmon")


class BackupError(NetworkAutomationError):
    """A backup file is missing or cannot be used."""


class BackupManager:
    """Manage configuration backups on disk."""

    TIME_FORMAT = "%Y%m%d-%H%M%S"

    def __init__(self, backup_dir: Path) -> None:
        self._backup_dir = Path(backup_dir)

    @property
    def backup_dir(self) -> Path:
        """Root folder of all backups."""
        return self._backup_dir

    def backup(self, device: NetworkDevice) -> Path:
        """Save ``device.backup_config()`` to a new timestamped file and return its path."""
        text = device.backup_config()
        folder = self._backup_dir / device.name
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime(self.TIME_FORMAT)
        path = folder / f"{device.name}_{stamp}.cfg"
        counter = 1
        while path.exists():  # two backups in the same second
            path = folder / f"{device.name}_{stamp}-{counter}.cfg"
            counter += 1
        path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        logger.info("%s: backup saved to %s", device.name, path)
        return path

    def list_backups(self, device_name: str) -> List[Path]:
        """Backups of one device, oldest first."""
        folder = self._backup_dir / device_name
        if not folder.exists():
            return []
        return sorted(folder.glob(f"{device_name}_*.cfg"), key=lambda p: (p.stat().st_mtime, p.name))

    def diff(self, old: Path, new: Path) -> str:
        """Unified diff between two backup files (``difflib``); empty string if identical."""
        old, new = Path(old), Path(new)
        for path in (old, new):
            if not path.exists():
                raise BackupError(f"Backup file not found: {path}")
        lines = difflib.unified_diff(
            old.read_text(encoding="utf-8").splitlines(),
            new.read_text(encoding="utf-8").splitlines(),
            fromfile=old.name,
            tofile=new.name,
            lineterm="",
        )
        return "\n".join(lines)

    def rollback(self, device: NetworkDevice, backup_file: Path) -> str:
        """Push the configuration stored in ``backup_file`` back to the device.

        The device computes the commands from the difference between its current
        configuration and the saved one (``rollback_commands``), so only the
        changed lines are sent.
        """
        backup_file = Path(backup_file)
        if not backup_file.exists():
            raise BackupError(f"Backup file not found: {backup_file}")
        target = backup_file.read_text(encoding="utf-8")
        commands = device.rollback_commands(device.backup_config(), target)
        if not commands:
            logger.info("%s: already matches %s, nothing to roll back", device.name, backup_file.name)
            return "Nothing to roll back."
        logger.warning("%s: rolling back to %s (%d command(s))", device.name, backup_file.name, len(commands))
        try:
            output = device.push_config(commands)
        except ConfigPushError:
            logger.error("%s: rollback to %s failed", device.name, backup_file.name)
            raise
        return "\n".join(commands) + "\n" + output
