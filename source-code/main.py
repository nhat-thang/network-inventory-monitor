"""Command-line entry point.

Run from the ``source-code`` directory, e.g. ``python main.py scan --group core``.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from backup import BackupManager
from collectors import FactsCollector
from core.connection_manager import ConnectionManager
from inventory import Inventory
from monitoring import HighCpuRule, InterfaceDownRule, MonitoringEngine, OspfNeighborLostRule
from provisioning import ConfigPusher
from reporting import AppLogger, HtmlReport

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
INVENTORY_FILE = BASE_DIR / "inventory.yaml"


def _selected_devices(args: argparse.Namespace):
    inventory = Inventory(INVENTORY_FILE).load()
    records = inventory.filter(group=args.group, role=args.role, tag=args.tag)
    return inventory.build_devices(records)


def cmd_inventory_list(args: argparse.Namespace) -> None:
    inventory = Inventory(INVENTORY_FILE).load()
    for record in inventory.filter(group=args.group, role=args.role, tag=args.tag):
        group = record.get("group", "")
        print(f"{record['name']:<8} {record['host']:<16} {record['device_type']:<10} {group}")


def cmd_scan(args: argparse.Namespace) -> None:
    devices = _selected_devices(args)
    facts, failures = FactsCollector(ConnectionManager(args.workers)).collect(devices)
    engine = MonitoringEngine(
        [InterfaceDownRule(), HighCpuRule(args.cpu_threshold), OspfNeighborLostRule()],
        snapshot_dir=OUTPUT_DIR / "snapshots",
    )
    alerts = engine.evaluate(facts, failures)
    engine.save_snapshot(facts)
    FactsCollector.to_json(facts, OUTPUT_DIR / "facts.json")
    FactsCollector.to_csv(facts, OUTPUT_DIR / "facts.csv")
    report = HtmlReport().render(facts, failures, alerts, OUTPUT_DIR / "report.html")
    print(f"{len(facts)} online, {len(failures)} offline, {len(alerts)} alert(s). Report: {report}")


def cmd_backup(args: argparse.Namespace) -> None:
    manager = BackupManager(OUTPUT_DIR / "backups")
    results = ConnectionManager(args.workers).run(_selected_devices(args), manager.backup)
    for r in results:
        print(f"{r.device}: {r.result if r.success else 'FAILED - ' + str(r.error)}")


def cmd_diff(args: argparse.Namespace) -> None:
    manager = BackupManager(OUTPUT_DIR / "backups")
    files = manager.list_backups(args.device)
    if len(files) < 2:
        print(f"{args.device}: need at least 2 backups to compare")
        return
    print(manager.diff(files[-2], files[-1]) or "No changes.")


def cmd_rollback(args: argparse.Namespace) -> None:
    manager = BackupManager(OUTPUT_DIR / "backups")
    inventory = Inventory(INVENTORY_FILE).load()
    records = [r for r in inventory.records if r["name"] == args.device]
    if not records:
        print(f"Unknown device: {args.device}")
        return
    device = inventory.build_devices(records)[0]
    with device:
        print(manager.rollback(device, Path(args.file)))


def cmd_deploy_ospf(args: argparse.Namespace) -> None:
    import yaml

    variables = yaml.safe_load((BASE_DIR / "provisioning" / "ospf_vars.yaml").read_text(encoding="utf-8"))
    inventory = Inventory(INVENTORY_FILE).load()
    records = inventory.filter(group=args.group, role=args.role, tag=args.tag)
    pusher = ConfigPusher(BASE_DIR / "provisioning" / "templates", BackupManager(OUTPUT_DIR / "backups"))
    for record, device in zip(records, inventory.build_devices(records)):
        lines = pusher.render(device, record["device_type"], variables[record["name"]])
        if args.dry_run:
            print(f"--- {device.name} (dry-run) ---")
            print(device.push_config(lines, dry_run=True))
            continue
        with device:
            print(f"--- {device.name} ---")
            print(pusher.deploy(device, lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netmon", description="Network inventory & status monitoring")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_filters(p: argparse.ArgumentParser) -> None:
        p.add_argument("--group", help="only devices in this group")
        p.add_argument("--role", help="only devices with this role")
        p.add_argument("--tag", help="only devices with this tag")
        p.add_argument("--workers", type=int, default=8, help="concurrent SSH sessions")

    inv = sub.add_parser("inventory", help="inventory operations")
    inv_sub = inv.add_subparsers(dest="action", required=True)
    inv_list = inv_sub.add_parser("list", help="list devices")
    add_filters(inv_list)
    inv_list.set_defaults(func=cmd_inventory_list)

    scan = sub.add_parser("scan", help="collect facts, detect anomalies, write reports")
    add_filters(scan)
    scan.add_argument("--cpu-threshold", type=float, default=80.0)
    scan.set_defaults(func=cmd_scan)

    bak = sub.add_parser("backup", help="back up running configs")
    add_filters(bak)
    bak.set_defaults(func=cmd_backup)

    diff = sub.add_parser("diff", help="compare the two latest backups of a device")
    diff.add_argument("device")
    diff.set_defaults(func=cmd_diff)

    rb = sub.add_parser("rollback", help="restore a device from a backup file")
    rb.add_argument("device")
    rb.add_argument("file")
    rb.set_defaults(func=cmd_rollback)

    ospf = sub.add_parser("deploy-ospf", help="configure OSPF from templates")
    add_filters(ospf)
    ospf.add_argument("--dry-run", action="store_true", help="show config without applying")
    ospf.set_defaults(func=cmd_deploy_ospf)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    AppLogger(OUTPUT_DIR / "logs")
    try:
        args.func(args)
    except NotImplementedError as exc:
        print(f"Not implemented yet: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
