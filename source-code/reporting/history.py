"""Operation history: one JSON line per action (who, what, which devices, result)."""

import getpass
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class HistoryLog:
    """Append-only history stored in a JSON Lines file."""

    _lock = threading.Lock()

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def record(self, action: str, devices: List[str], ok: int, failed: int,
               detail: Optional[str] = None, source: str = "cli") -> Dict[str, Any]:
        """Add one entry and return it."""
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "user": _user(),
            "source": source,
            "action": action,
            "devices": devices,
            "ok": ok,
            "failed": failed,
            "detail": detail or "",
        }
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def entries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Newest first."""
        if not self._path.exists():
            return []
        items = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            try:
                items.append(json.loads(line))
            except ValueError:
                continue
        items.reverse()
        return items[:limit] if limit else items


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "unknown"
