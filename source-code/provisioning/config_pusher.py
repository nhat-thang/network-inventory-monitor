"""Render a template per device and push it, rolling back on failure.

Template file per vendor: ``templates/ospf_<device_type>.j2``.
Variables per device: ``ospf_vars.yaml``.
"""

from pathlib import Path
from typing import Any, Dict, List

from backup.backup_manager import BackupManager
from devices.base import NetworkDevice


class ConfigPusher:
    """Render and apply configuration to many devices."""

    def __init__(self, template_dir: Path, backup_manager: BackupManager) -> None:
        self._template_dir = Path(template_dir)
        self._backups = backup_manager

    # TODO (provisioning): implement every method below.
    def render(self, device: NetworkDevice, device_type: str, variables: Dict[str, Any]) -> List[str]:
        """Render the vendor template into a list of config lines.

        Derive ``ip``, ``netmask``, ``prefixlen`` and ``network`` from each
        interface's ``address`` (e.g. ``10.0.12.1/30``) with ``ipaddress``.
        """
        raise NotImplementedError("ConfigPusher.render")

    def deploy(self, device: NetworkDevice, lines: List[str], dry_run: bool = False) -> str:
        """Back up, push ``lines`` and roll back automatically if the push fails."""
        raise NotImplementedError("ConfigPusher.deploy")
