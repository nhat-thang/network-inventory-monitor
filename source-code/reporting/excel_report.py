"""Excel report of a scan (one workbook, one sheet per topic)."""

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from core.models import Alert, DeviceFacts, TaskResult

SEVERITY_LABEL = {"critical": "Nghiêm trọng", "warning": "Cảnh báo", "info": "Thông tin"}
SEVERITY_FILL = {"critical": "F8D7DA", "warning": "FFF3CD", "info": "D1ECF1"}


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


class ExcelReport:
    """Write facts, failures and alerts of one scan to an .xlsx workbook."""

    HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
    THIN = Side(style="thin", color="A6A6A6")
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

    def render(
        self,
        facts: List[DeviceFacts],
        failures: List[TaskResult],
        alerts: List[Alert],
        output_path: Path,
        generated_at: Optional[datetime] = None,
    ) -> Path:
        """Create the workbook and return its path."""
        generated_at = generated_at or datetime.now()
        alerts = sorted(alerts, key=lambda a: (a.rank, a.device, a.rule))
        wb = Workbook()
        self._summary(wb.active, facts, failures, alerts, generated_at)
        self._devices(wb.create_sheet("Thiết bị"), facts, failures)
        self._alerts(wb.create_sheet("Cảnh báo"), alerts)
        self._table(wb.create_sheet("Cổng"), ["Thiết bị", "Cổng", "Địa chỉ IP", "Admin", "Link"],
                    [[f.device, i.name, i.ip_address or "", "up" if i.admin_up else "down",
                      "up" if i.oper_up else "down"] for f in facts for i in f.interfaces])
        self._table(wb.create_sheet("Định tuyến"), ["Thiết bị", "Prefix", "Giao thức", "Next hop", "Cổng"],
                    [[f.device, r.prefix, r.protocol, r.next_hop or "", r.interface or ""]
                     for f in facts for r in f.routes])
        self._table(wb.create_sheet("OSPF"), ["Thiết bị", "Router ID", "Địa chỉ", "Cổng", "Trạng thái"],
                    [[f.device, n.neighbor_id, n.address, n.interface, n.state]
                     for f in facts for n in f.ospf_neighbors])
        self._table(wb.create_sheet("LLDP"), ["Thiết bị", "Cổng", "Láng giềng", "Cổng láng giềng", "Nền tảng"],
                    [[f.device, n.local_interface, n.neighbor, n.neighbor_port or "", n.platform or ""]
                     for f in facts for n in f.lldp_neighbors])
        self._table(wb.create_sheet("ARP"), ["Thiết bị", "IP", "MAC", "Cổng"],
                    [[f.device, e["ip"], e["mac"], e.get("interface", "")] for f in facts for e in f.arp_entries])
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return output_path

    # --------------------------------------------------------------- sheets
    def _summary(self, ws: Worksheet, facts, failures, alerts, generated_at: datetime) -> None:
        ws.title = "Tổng quan"
        count = Counter(a.severity for a in alerts)
        rows = [
            ["Báo cáo kiểm kê và giám sát trạng thái mạng"],
            [],
            ["Thời điểm quét", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
            ["Tổng số thiết bị", len(facts) + len(failures)],
            ["Trực tuyến", len(facts)],
            ["Mất kết nối", len(failures)],
            ["Cảnh báo nghiêm trọng", count["critical"]],
            ["Cảnh báo", count["warning"]],
            ["Thông tin", count["info"]],
        ]
        for row in rows:
            ws.append(row)
        ws["A1"].font = Font(bold=True, size=14)
        for r in range(3, len(rows) + 1):
            ws.cell(r, 1).font = Font(bold=True)
            for c in (1, 2):
                ws.cell(r, c).border = self.BORDER
        ws.column_dimensions["A"].width = 26
        ws.column_dimensions["B"].width = 22

    def _devices(self, ws: Worksheet, facts: List[DeviceFacts], failures: List[TaskResult]) -> None:
        head = ["Thiết bị", "Trạng thái", "Hãng", "Phiên bản", "Hostname", "Serial / ID", "Uptime",
                "CPU (%)", "RAM (%)", "RAM (MB)", "Cổng up", "Số route", "OSPF Full", "LLDP"]
        rows: List[List[Any]] = []
        for f in facts:
            rows.append([
                f.device, "Trực tuyến", f.vendor, f.os_version or "", f.hostname or "", f.serial or "",
                humanize_seconds(f.uptime_seconds), f.cpu_percent, f.memory_percent, f.memory_total_mb,
                f"{sum(i.oper_up for i in f.interfaces)}/{len(f.interfaces)}", len(f.routes),
                sum(n.state.lower().startswith("full") for n in f.ospf_neighbors), len(f.lldp_neighbors),
            ])
        for r in failures:
            rows.append([r.device, "Mất kết nối", "", r.error or ""] + [""] * (len(head) - 4))
        self._table(ws, head, sorted(rows, key=lambda x: x[0]))
        for row in ws.iter_rows(min_row=2):
            if row[1].value == "Mất kết nối":
                for cell in row:
                    cell.fill = PatternFill("solid", fgColor=SEVERITY_FILL["critical"])

    def _alerts(self, ws: Worksheet, alerts: List[Alert]) -> None:
        self._table(ws, ["Mức độ", "Thiết bị", "Luật", "Nội dung", "Thời gian"],
                    [[SEVERITY_LABEL.get(a.severity, a.severity), a.device, a.rule, a.message,
                      a.timestamp.strftime("%Y-%m-%d %H:%M:%S")] for a in alerts])
        for row, alert in zip(ws.iter_rows(min_row=2), alerts):
            row[0].fill = PatternFill("solid", fgColor=SEVERITY_FILL.get(alert.severity, "FFFFFF"))

    def _table(self, ws: Worksheet, head: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        ws.append(list(head))
        for row in rows:
            ws.append(list(row))
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(vertical="center")
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=len(head)):
            for cell in row:
                cell.border = self.BORDER
        for idx in range(1, len(head) + 1):
            values = [str(ws.cell(r, idx).value or "") for r in range(1, ws.max_row + 1)]
            ws.column_dimensions[get_column_letter(idx)].width = min(max(len(v) for v in values) + 2, 60)
        ws.freeze_panes = "A2"
        if rows:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(head))}{ws.max_row}"
