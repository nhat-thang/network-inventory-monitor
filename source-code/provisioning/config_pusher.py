"""Render a template per device and push it, rolling back on failure.

Template file per vendor: ``templates/ospf_<device_type>.j2``.
Variables per device: ``ospf_vars.yaml``.
"""

import ipaddress
import logging
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from backup.backup_manager import BackupManager
from core.exceptions import ConfigPushError, NetworkAutomationError
from devices.base import NetworkDevice

logger = logging.getLogger("netmon")


class TemplateError(NetworkAutomationError):
    """A template or its variables are missing or invalid."""


class ConfigPusher:
    """Render and apply configuration to many devices."""

    def __init__(self, template_dir: Path, backup_manager: BackupManager, template: str = "ospf") -> None:
        self._template_dir = Path(template_dir)
        self._backups = backup_manager
        self._template = template
        self._env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, device: NetworkDevice, device_type: str, variables: Dict[str, Any]) -> List[str]:
        """Render the vendor template into a list of config lines.

        Derive ``ip``, ``netmask``, ``prefixlen`` and ``network`` from each
        interface's ``address`` (e.g. ``10.0.12.1/30``) with ``ipaddress``.
        """
        name = f"{self._template}_{device_type}.j2"
        try:
            template = self._env.get_template(name)
        except TemplateNotFound as exc:
            raise TemplateError(f"{device.name}: no template {name} in {self._template_dir}") from exc
        context = dict(variables)
        interfaces = []
        for intf in variables.get("interfaces", []):
            try:
                iface = ipaddress.ip_interface(intf["address"])
            except (KeyError, ValueError) as exc:
                raise TemplateError(f"{device.name}: bad interface entry {intf!r}") from exc
            interfaces.append({
                **intf,
                "ip": str(iface.ip),
                "netmask": str(iface.netmask),
                "prefixlen": iface.network.prefixlen,
                "network": str(iface.network),
                "network_address": str(iface.network.network_address),
            })
        context["interfaces"] = interfaces
        try:
            text = template.render(**context)
        except Exception as exc:  # noqa: BLE001 - undefined variable, bad filter...
            raise TemplateError(f"{device.name}: cannot render {name}: {exc}") from exc
        return [line.rstrip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]

    def deploy(self, device: NetworkDevice, lines: List[str], dry_run: bool = False) -> str:
        """Back up, push ``lines`` and roll back automatically if the push fails."""
        if dry_run:
            return device.push_config(lines, dry_run=True)
        backup_file = self._backups.backup(device)
        try:
            output = device.push_config(lines)
        except ConfigPushError as exc:
            logger.error("%s: push failed (%s), rolling back to %s", device.name, exc, backup_file.name)
            try:
                self._backups.rollback(device, backup_file)
            except Exception as rb_exc:  # noqa: BLE001
                raise ConfigPushError(
                    f"{device.name}: push failed and rollback failed too: {rb_exc}") from exc
            raise ConfigPushError(f"{device.name}: push failed, configuration rolled back: {exc}") from exc
        logger.info("%s: %d config line(s) applied (backup %s)", device.name, len(lines), backup_file.name)
        return output
