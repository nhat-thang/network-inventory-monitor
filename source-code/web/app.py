"""Flask application: pages and routes of the web interface.

Run with ``python main.py web`` (or ``python -m web.app``) from ``source-code``.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, Response, abort, flash, redirect, render_template, request, send_file, url_for

from core.exceptions import NetworkAutomationError
from reporting import AppLogger
from services import NetworkService
from web.tasks import TaskManager

ACTIONS = {"scan": "Quét thiết bị", "backup": "Sao lưu cấu hình", "deploy": "Áp cấu hình", "rollback": "Khôi phục"}


def create_app(base_dir: Path, output_dir: Path, demo: bool = False) -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.secret_key = "netmon-local-ui"
    AppLogger(Path(output_dir) / "logs")
    service = NetworkService(base_dir, output_dir, source="web")
    tasks = TaskManager()
    app.jinja_env.globals["demo_mode"] = demo

    @app.template_filter("uptime")
    def _uptime(seconds):
        from reporting.markdown_report import humanize_seconds

        return humanize_seconds(seconds)

    @app.errorhandler(NetworkAutomationError)
    def _error(exc):
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("dashboard"))

    # ------------------------------------------------------------ pages
    @app.route("/")
    def dashboard():
        data = service.dashboard()
        return render_template("dashboard.html", d=data, tasks=tasks.recent(5), actions=ACTIONS)

    @app.route("/devices")
    def devices():
        group, tag = request.args.get("group") or None, request.args.get("tag") or None
        inventory = service.inventory()
        records = inventory.filter(group=group, tag=tag)
        groups = sorted({r.get("group") for r in inventory.records if r.get("group")})
        tags = sorted({t for r in inventory.records for t in r.get("tags", [])})
        last = service.last_scan() or {}
        offline = {o["device"]: o["error"] for o in last.get("offline", [])}
        return render_template("devices.html", records=records, facts=service.last_facts(), offline=offline,
                               groups=groups, tags=tags, group=group, tag=tag,
                               templates=service.templates(), last=last)

    @app.route("/devices/<name>")
    def device(name: str):
        record = service.inventory().get(name)
        facts = service.last_facts().get(name)
        return render_template("device.html", record=record, f=facts,
                               backups=list(reversed(service.backups.list_backups(name))))

    @app.route("/tasks", methods=["POST"])
    def start_task():
        action = request.form.get("action", "")
        names = request.form.getlist("device")
        if not names:
            flash("Chưa chọn thiết bị nào.", "error")
            return redirect(url_for("devices"))
        records = service.select(names)
        reports_url, backups_url = url_for("reports"), url_for("backups")  # built here: no request context in the thread
        if action == "scan":
            def work(on_result) -> Dict[str, Any]:
                result = service.scan(records, on_result)
                return {"message": f"{len(result.facts)} trực tuyến, {len(result.failures)} mất kết nối, "
                                   f"{len(result.alerts)} cảnh báo",
                        "alerts": [{"device": a.device, "severity": a.severity, "message": a.message}
                                   for a in result.alerts],
                        "link": f"{reports_url}/{result.report_path.name}",
                        "link_text": f"Xem báo cáo {result.report_path.name}"}
        elif action == "backup":
            def work(on_result) -> Dict[str, Any]:
                results = service.backup(records, lambda r: on_result(_named(r)))
                ok = sum(r.success for r in results)
                return {"message": f"Đã sao lưu {ok}/{len(results)} thiết bị",
                        "link": backups_url, "link_text": "Xem các bản sao lưu"}
        elif action == "deploy":
            template = request.form.get("template", "")
            dry_run = request.form.get("dry_run") == "1"
            if template not in service.templates():
                abort(400)
            action = f"deploy {template}" + (" (dry-run)" if dry_run else "")

            def work(on_result) -> Dict[str, Any]:
                results = service.deploy(template, records, dry_run=dry_run, on_result=on_result)
                ok = sum(r.success for r in results)
                verb = "Xem trước" if dry_run else "Đã áp"
                return {"message": f"{verb} cấu hình {template}: {ok}/{len(results)} thiết bị thành công"}
        else:
            abort(400)
        task = tasks.start(action, names, work)
        return redirect(url_for("task_page", task_id=task.id))

    @app.route("/tasks/<int:task_id>")
    def task_page(task_id: int):
        task = tasks.get(task_id) or abort(404)
        return render_template("task.html", task=task, actions=ACTIONS)

    @app.route("/tasks/<int:task_id>/events")
    def task_events(task_id: int):
        task = tasks.get(task_id) or abort(404)

        def stream():
            for event in tasks.follow(task):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return Response(stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})

    # ---------------------------------------------------------- backups
    @app.route("/backups")
    def backups():
        return render_template("backups.html", backups=service.list_backups())

    @app.route("/backups/<device>/<file_name>")
    def backup_view(device: str, file_name: str):
        path = service.backup_file(device, file_name)
        if request.args.get("download"):
            return send_file(path, as_attachment=True, download_name=path.name)
        return render_template("backup_view.html", device=device, path=path,
                               text=path.read_text(encoding="utf-8"),
                               others=[p.name for p in service.backups.list_backups(device) if p.name != path.name])

    @app.route("/backups/<device>/diff")
    def backup_diff(device: str):
        old, new = request.args.get("old", ""), request.args.get("new", "")
        return render_template("diff.html", device=device, old=old, new=new, diff=service.diff(device, old, new))

    @app.route("/backups/<device>/<file_name>/rollback", methods=["POST"])
    def backup_rollback(device: str, file_name: str):
        service.backup_file(device, file_name)  # 404-like error if missing

        def work(on_result) -> Dict[str, Any]:
            from core.models import TaskResult

            try:
                output = service.rollback(device, file_name)
                on_result(TaskResult(device, True, output))
            except Exception as exc:  # noqa: BLE001
                on_result(TaskResult(device, False, error=f"{type(exc).__name__}: {exc}"))
            return {"message": f"Khôi phục {device} về {file_name}"}

        task = tasks.start(f"rollback {file_name}", [device], work)
        return redirect(url_for("task_page", task_id=task.id))

    # --------------------------------------------------- reports/history
    @app.route("/reports")
    def reports():
        return render_template("reports.html", reports=service.reports())

    @app.route("/reports/<name>")
    def download_report(name: str):
        path = service.report_file(name)
        if request.args.get("download"):
            return send_file(path, as_attachment=True, download_name=path.name, mimetype="text/markdown")
        return render_template("report_view.html", path=path, text=path.read_text(encoding="utf-8"))

    @app.route("/history")
    def history():
        return render_template("history.html", entries=service.history.entries())

    return app


def _named(result):
    """Show only the file name of a backup in the progress list."""
    if result.success and result.result is not None:
        result.result = f"Đã lưu {Path(result.result).name}"
    return result


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    create_app(base, base / "output").run(threaded=True)
