"""Command-line entry point.

Run from the ``source-code`` directory, e.g. ``python main.py scan --group core``.
The CLI only parses arguments and prints results; all work is done by
``services.NetworkService``, the same class the web interface uses.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from core.exceptions import NetworkAutomationError
from core.models import TaskResult
from core.scheduler import PeriodicRunner
from reporting import AppLogger
from services import NetworkService

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

logger = logging.getLogger("netmon")


def _service(args: argparse.Namespace) -> NetworkService:
    return NetworkService(
        BASE_DIR,
        OUTPUT_DIR,
        workers=getattr(args, "workers", 8),
        cpu_threshold=getattr(args, "cpu_threshold", 80.0),
        memory_threshold=getattr(args, "memory_threshold", 90.0),
    )


def _records(service: NetworkService, args: argparse.Namespace):
    return service.select(getattr(args, "devices", None), args.group, args.role, args.tag)


def _print_progress(result: TaskResult) -> None:
    status = "OK  " if result.success else "LỖI"
    print(f"  [{status}] {result.device}" + ("" if result.success else f": {result.error}"))


# ------------------------------------------------------------- inventory
def cmd_inventory_list(args: argparse.Namespace) -> None:
    for record in _service(args).select(None, args.group, args.role, args.tag):
        group = record.get("group", "")
        tags = ",".join(record.get("tags", []))
        print(f"{record['name']:<8} {record['host']:<16} {record['device_type']:<18} {group:<8} {tags}")


def _record_from_args(args: argparse.Namespace) -> dict:
    fields = ("host", "port", "device_type", "group", "role", "credentials")
    record = {f: getattr(args, f) for f in fields if getattr(args, f, None) is not None}
    if args.tags is not None:
        record["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
    return record


def cmd_inventory_add(args: argparse.Namespace) -> None:
    service = _service(args)
    inventory = service.inventory()
    inventory.add({"name": args.name, **_record_from_args(args)})
    inventory.save()
    service.history.record("inventory add", [args.name], 1, 0)
    logger.info("inventory: added device %s", args.name)
    print(f"Added {args.name}.")


def cmd_inventory_edit(args: argparse.Namespace) -> None:
    service = _service(args)
    inventory = service.inventory()
    changes = _record_from_args(args)
    if args.new_name:
        changes["name"] = args.new_name
    inventory.update(args.name, **changes)
    inventory.save()
    service.history.record("inventory edit", [args.name], 1, 0, str(changes))
    logger.info("inventory: updated device %s %s", args.name, changes)
    print(f"Updated {args.name}.")


def cmd_inventory_remove(args: argparse.Namespace) -> None:
    service = _service(args)
    inventory = service.inventory()
    inventory.remove(args.name)
    inventory.save()
    service.history.record("inventory remove", [args.name], 1, 0)
    logger.info("inventory: removed device %s", args.name)
    print(f"Removed {args.name}.")


# ----------------------------------------------------------------- tasks
def cmd_scan(args: argparse.Namespace) -> None:
    service = _service(args)
    result = service.scan(_records(service, args), on_result=_print_progress)
    print(f"{len(result.facts)} online, {len(result.failures)} offline, {len(result.alerts)} alert(s). "
          f"Report: {result.report_path}")


def cmd_backup(args: argparse.Namespace) -> None:
    service = _service(args)
    records = _records(service, args)

    def run_once() -> None:
        for r in service.backup(records):
            print(f"{r.device}: {r.result if r.success else 'FAILED - ' + str(r.error)}")

    if args.every is None:
        run_once()
        return
    print(f"Scheduled backup every {args.every} minute(s)" + (f", {args.times} time(s)" if args.times else "")
          + ". Press Ctrl+C to stop.")
    runner = PeriodicRunner(run_once, args.every, args.times)
    try:
        runner.run()
    except KeyboardInterrupt:
        runner.stop()
        print(f"Stopped after {runner.runs} run(s).")


def cmd_diff(args: argparse.Namespace) -> None:
    service = _service(args)
    files = service.backups.list_backups(args.device)
    if len(files) < 2:
        print(f"{args.device}: need at least 2 backups to compare")
        return
    print(service.diff(args.device, files[-2].name, files[-1].name) or "No changes.")


def cmd_rollback(args: argparse.Namespace) -> None:
    print(_service(args).rollback(args.device, Path(args.file).name))


def cmd_deploy(args: argparse.Namespace) -> None:
    service = _service(args)
    records = _records(service, args)
    if args.dry_run:
        for device, lines in service.render(args.template, records).items():
            print(f"--- {device} (dry-run, {len(lines)} line(s)) ---")
            print("\n".join(lines))
        return
    results = service.deploy(args.template, records, on_result=_print_progress)
    failed = [r.device for r in results if not r.success]
    if failed:
        print(f"Failed on: {', '.join(failed)}")


def cmd_deploy_ospf(args: argparse.Namespace) -> None:
    args.template = "ospf"
    cmd_deploy(args)


def cmd_web(args: argparse.Namespace) -> None:
    from web.app import create_app

    print(f"Web interface: http://{args.host}:{args.port}  (Ctrl+C to stop)")
    create_app(BASE_DIR, OUTPUT_DIR).run(host=args.host, port=args.port, threaded=True)


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netmon", description="Network inventory & status monitoring")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_filters(p: argparse.ArgumentParser) -> None:
        p.add_argument("--group", help="only devices in this group")
        p.add_argument("--role", help="only devices with this role")
        p.add_argument("--tag", help="only devices with this tag")
        p.add_argument("--devices", nargs="+", metavar="NAME", help="only these devices")
        p.add_argument("--workers", type=int, default=8, help="concurrent SSH sessions")

    inv = sub.add_parser("inventory", help="inventory operations")
    inv_sub = inv.add_subparsers(dest="action", required=True)
    inv_list = inv_sub.add_parser("list", help="list devices")
    add_filters(inv_list)
    inv_list.set_defaults(func=cmd_inventory_list)

    def add_record_fields(p: argparse.ArgumentParser, required: bool) -> None:
        p.add_argument("--host", required=required, help="management IP")
        p.add_argument("--device-type", dest="device_type", required=required,
                       help="mikrotik_routeros | vyos | cisco_ios")
        p.add_argument("--port", type=int, help="SSH port (default 22)")
        p.add_argument("--group")
        p.add_argument("--role")
        p.add_argument("--tags", help="comma-separated, e.g. vyos,ospf")
        p.add_argument("--credentials", help="env prefix for this device's account, e.g. LAB")

    inv_add = inv_sub.add_parser("add", help="add a device")
    inv_add.add_argument("name")
    add_record_fields(inv_add, required=True)
    inv_add.set_defaults(func=cmd_inventory_add)

    inv_edit = inv_sub.add_parser("edit", help="change fields of a device")
    inv_edit.add_argument("name")
    inv_edit.add_argument("--new-name", dest="new_name")
    add_record_fields(inv_edit, required=False)
    inv_edit.set_defaults(func=cmd_inventory_edit)

    inv_rm = inv_sub.add_parser("remove", help="delete a device")
    inv_rm.add_argument("name")
    inv_rm.set_defaults(func=cmd_inventory_remove)

    scan = sub.add_parser("scan", help="collect facts, detect anomalies, write the Markdown report")
    add_filters(scan)
    scan.add_argument("--cpu-threshold", type=float, default=80.0)
    scan.add_argument("--memory-threshold", type=float, default=90.0)
    scan.set_defaults(func=cmd_scan)

    bak = sub.add_parser("backup", help="back up running configs (once or on a schedule)")
    add_filters(bak)
    bak.add_argument("--every", type=float, metavar="MINUTES", help="repeat every N minutes")
    bak.add_argument("--times", type=int, help="stop after this many runs (with --every)")
    bak.set_defaults(func=cmd_backup)

    diff = sub.add_parser("diff", help="compare the two latest backups of a device")
    diff.add_argument("device")
    diff.set_defaults(func=cmd_diff)

    rb = sub.add_parser("rollback", help="restore a device from a backup file")
    rb.add_argument("device")
    rb.add_argument("file")
    rb.set_defaults(func=cmd_rollback)

    dep = sub.add_parser("deploy", help="apply a template (ospf, baseline) to many devices")
    dep.add_argument("template", help="template name, e.g. ospf or baseline")
    add_filters(dep)
    dep.add_argument("--dry-run", action="store_true", help="show config without applying")
    dep.set_defaults(func=cmd_deploy)

    ospf = sub.add_parser("deploy-ospf", help="same as: deploy ospf")
    add_filters(ospf)
    ospf.add_argument("--dry-run", action="store_true", help="show config without applying")
    ospf.set_defaults(func=cmd_deploy_ospf)

    web = sub.add_parser("web", help="start the web interface")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=5000)
    web.set_defaults(func=cmd_web)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    AppLogger(OUTPUT_DIR / "logs")
    try:
        args.func(args)
    except NetworkAutomationError as exc:
        logger.error("%s: %s", type(exc).__name__, exc)
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
