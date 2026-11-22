"""HTML dashboard report: device status overview and alert list.

The page is one self-contained file (inline CSS, no JavaScript, no internet
needed), so it can be opened directly from disk or attached to the report.
"""

import getpass
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.models import Alert, DeviceFacts, TaskResult

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def humanize_seconds(seconds: Optional[int]) -> str:
    """``93784`` -> ``1d 2h 3m``."""
    if seconds is None:
        return "—"
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class HtmlReport:
    """Render scan results into a single self-contained HTML file."""

    def __init__(self, template_name: str = "dashboard.html.j2", cpu_threshold: float = 80.0) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.filters["uptime"] = humanize_seconds
        self._template_name = template_name
        self._cpu_threshold = cpu_threshold

    def build_context(
        self,
        facts: List[DeviceFacts],
        failures: List[TaskResult],
        alerts: List[Alert],
    ) -> Dict[str, Any]:
        """Numbers and rows shown on the page (separate from rendering so it can be tested)."""
        severity = Counter(a.severity for a in alerts)
        alerts_by_device = Counter(a.device for a in alerts if a.severity != "info")
        devices = []
        for f in facts:
            down = f.interfaces_down
            status = "critical" if any(
                a.device == f.device and a.severity == "critical" for a in alerts
            ) else ("warning" if alerts_by_device[f.device] else "good")
            devices.append({
                "facts": f,
                "online": True,
                "status": status,
                "interfaces_up": sum(1 for i in f.interfaces if i.oper_up),
                "interfaces_down": down,
                "ospf_full": sum(1 for n in f.ospf_neighbors if n.state.lower().startswith("full")),
                "alerts": [a for a in alerts if a.device == f.device],
            })
        for r in failures:
            devices.append({"facts": None, "name": r.device, "online": False, "status": "critical",
                            "error": r.error, "alerts": [a for a in alerts if a.device == r.device]})
        devices.sort(key=lambda d: d["facts"].device if d["facts"] else d["name"])
        total = len(facts) + len(failures)
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator": _operator(),
            "total": total,
            "online": len(facts),
            "offline": len(failures),
            "critical": severity["critical"],
            "warning": severity["warning"],
            "info": severity["info"],
            "interfaces_down": sum(len(f.interfaces_down) for f in facts),
            "devices": devices,
            "alerts": sorted(alerts, key=lambda a: (a.rank, a.device, a.rule)),
            "cpu_threshold": self._cpu_threshold,
        }

    def render(
        self,
        facts: List[DeviceFacts],
        failures: List[TaskResult],
        alerts: List[Alert],
        output_path: Path,
    ) -> Path:
        """Write the report and return its path.

        Content: number of devices online/offline, one row per device
        (name, vendor, version, uptime, CPU), and the alert list sorted by severity.
        """
        html = self._env.get_template(self._template_name).render(
            **self.build_context(facts, failures, alerts)
        )
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return output_path


def _operator() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "unknown"
