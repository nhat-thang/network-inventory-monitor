"""Markdown report of a scan: plain text, readable as-is and rendered by GitHub, VS Code, etc."""

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Sequence

from core.models import Alert, DeviceFacts, TaskResult

SEVERITY_LABEL = {"critical": "NGHIÊM TRỌNG", "warning": "CẢNH BÁO", "info": "THÔNG TIN"}


def humanize_seconds(seconds: Optional[int]) -> str:
    """``93784`` -> ``1d 2h 3m``; ``66`` -> ``1m 6s``."""
    if seconds is None:
        return "-"
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _cell(value: Any) -> str:
    """Text safe to put in a Markdown table cell."""
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        value = f"{value:.0f}"
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def md_table(head: Sequence[str], rows: Sequence[Sequence[Any]], right: Sequence[int] = ()) -> str:
    """Build a pipe table; ``right`` lists the columns to right-align."""
    if not rows:
        return "_Không có dữ liệu._\n"
    align = ["---:" if i in right else "---" for i in range(len(head))]
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join(align) + " |"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


class MarkdownReport:
    """Write facts, failures and alerts of one scan to a .md file."""

    def render(
        self,
        facts: List[DeviceFacts],
        failures: List[TaskResult],
        alerts: List[Alert],
        output_path: Path,
        generated_at: Optional[datetime] = None,
    ) -> Path:
        """Create the report and return its path."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.build(facts, failures, alerts, generated_at), encoding="utf-8")
        return output_path

    def build(
        self,
        facts: List[DeviceFacts],
        failures: List[TaskResult],
        alerts: List[Alert],
        generated_at: Optional[datetime] = None,
    ) -> str:
        """Return the report text."""
        generated_at = generated_at or datetime.now()
        alerts = sorted(alerts, key=lambda a: (a.rank, a.device, a.rule))
        facts = sorted(facts, key=lambda f: f.device)
        count = Counter(a.severity for a in alerts)
        parts = [
            "# Báo cáo kiểm kê và giám sát trạng thái mạng\n",
            f"Thời điểm quét: {generated_at:%Y-%m-%d %H:%M:%S}\n",
            "## 1. Tổng quan\n",
            md_table(["Chỉ số", "Giá trị"], [
                ["Tổng số thiết bị", len(facts) + len(failures)],
                ["Trực tuyến", len(facts)],
                ["Mất kết nối", len(failures)],
                ["Cảnh báo nghiêm trọng", count["critical"]],
                ["Cảnh báo", count["warning"]],
                ["Thông tin", count["info"]],
            ], right=[1]),
            "## 2. Cảnh báo\n",
            md_table(["Mức độ", "Thiết bị", "Luật", "Nội dung"],
                     [[SEVERITY_LABEL.get(a.severity, a.severity), a.device, f"`{a.rule}`", a.message]
                      for a in alerts]),
            "## 3. Thiết bị\n",
            self._devices(facts, failures),
            "## 4. Chi tiết từng thiết bị\n",
        ]
        for f in facts:
            parts.append(self._detail(f))
        if failures:
            parts.append("## 5. Thiết bị không kết nối được\n")
            parts.append(md_table(["Thiết bị", "Lỗi"], [[r.device, r.error] for r in sorted(failures, key=lambda r: r.device)]))
        return "\n".join(parts)

    @staticmethod
    def _devices(facts: List[DeviceFacts], failures: List[TaskResult]) -> str:
        rows: List[List[Any]] = []
        for f in facts:
            rows.append([
                f.device, "Trực tuyến", f.vendor, f.os_version, f.hostname,
                humanize_seconds(f.uptime_seconds),
                None if f.cpu_percent is None else f"{f.cpu_percent:.0f}%",
                None if f.memory_percent is None else f"{f.memory_percent:.0f}%",
                f"{sum(i.oper_up for i in f.interfaces)}/{len(f.interfaces)}", len(f.routes),
                sum(n.state.lower().startswith("full") for n in f.ospf_neighbors), len(f.lldp_neighbors),
            ])
        for r in failures:
            rows.append([r.device, "**Mất kết nối**"] + [None] * 10)
        rows.sort(key=lambda x: x[0])
        return md_table(["Thiết bị", "Trạng thái", "Hãng", "Phiên bản", "Hostname", "Uptime", "CPU", "RAM",
                         "Cổng up", "Route", "OSPF Full", "LLDP"], rows, right=[5, 6, 7, 8, 9, 10, 11])

    @staticmethod
    def _detail(f: DeviceFacts) -> str:
        memory = "-" if f.memory_percent is None else f"{f.memory_percent:.0f}% của {f.memory_total_mb:.0f} MB"
        return "\n".join([
            f"### {f.device} ({f.hostname or '-'})\n",
            f"- Phiên bản: {f.os_version or '-'}",
            f"- Serial / ID: `{f.serial or '-'}`",
            f"- Uptime: {humanize_seconds(f.uptime_seconds)}; CPU: "
            f"{'-' if f.cpu_percent is None else f'{f.cpu_percent:.0f}%'}; RAM: {memory}",
            f"- Mã băm cấu hình: `{(f.config_hash or '-')[:16]}`\n",
            "**Cổng**\n",
            md_table(["Cổng", "Địa chỉ IP", "Admin", "Link"],
                     [[i.name, i.ip_address, "up" if i.admin_up else "down", "up" if i.oper_up else "down"]
                      for i in f.interfaces]),
            "**Bảng định tuyến**\n",
            md_table(["Prefix", "Giao thức", "Next hop", "Cổng"],
                     [[r.prefix, r.protocol, r.next_hop, r.interface] for r in f.routes]),
            "**OSPF neighbor**\n",
            md_table(["Router ID", "Địa chỉ", "Cổng", "Trạng thái"],
                     [[n.neighbor_id, n.address, n.interface, n.state] for n in f.ospf_neighbors]),
            "**Láng giềng LLDP**\n",
            md_table(["Cổng", "Láng giềng", "Cổng láng giềng", "Nền tảng"],
                     [[n.local_interface, n.neighbor, n.neighbor_port, n.platform] for n in f.lldp_neighbors]),
            "**Bảng ARP**\n",
            md_table(["IP", "MAC", "Cổng"], [[e["ip"], e["mac"], e.get("interface")] for e in f.arp_entries]),
        ])
