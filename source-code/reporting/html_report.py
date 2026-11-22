"""HTML dashboard report: device status overview and alert list."""

from pathlib import Path
from typing import List

from core.models import Alert, DeviceFacts, TaskResult


class HtmlReport:
    """Render scan results into a single self-contained HTML file."""

    # TODO (reporting): implement, e.g. with a Jinja2 template.
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
        raise NotImplementedError("HtmlReport.render")
