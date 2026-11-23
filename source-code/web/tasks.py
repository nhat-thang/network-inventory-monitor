"""Background tasks with live progress for the web interface.

A task runs in its own thread. Each device result is appended to the task's
event list as soon as it is known; the browser reads the events through
Server-Sent Events, so progress shows up in real time.
"""

import itertools
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterator, List, Optional

from core.models import TaskResult


@dataclass
class WebTask:
    """One running or finished operation."""

    id: int
    action: str
    devices: List[str]
    started: datetime = field(default_factory=datetime.now)
    finished: Optional[datetime] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.finished is not None


class TaskManager:
    """Starts tasks and lets several readers follow their events."""

    def __init__(self) -> None:
        self._tasks: Dict[int, WebTask] = {}
        self._ids = itertools.count(1)
        self._cond = threading.Condition()

    def get(self, task_id: int) -> Optional[WebTask]:
        return self._tasks.get(task_id)

    def recent(self, limit: int = 10) -> List[WebTask]:
        return sorted(self._tasks.values(), key=lambda t: t.id, reverse=True)[:limit]

    def _emit(self, task: WebTask, event: Dict[str, Any]) -> None:
        with self._cond:
            event["time"] = datetime.now().strftime("%H:%M:%S")
            task.events.append(event)
            self._cond.notify_all()

    def start(self, action: str, devices: List[str],
              work: Callable[[Callable[[TaskResult], None]], Dict[str, Any]]) -> WebTask:
        """Run ``work(on_result)`` in a thread; ``work`` returns a summary dict."""
        task = WebTask(next(self._ids), action, devices)
        self._tasks[task.id] = task

        def on_result(result: TaskResult) -> None:
            detail = result.result if isinstance(result.result, str) else ""
            self._emit(task, {"type": "device", "device": result.device, "ok": result.success,
                              "detail": detail if result.success else (result.error or "")})

        def runner() -> None:
            self._emit(task, {"type": "start", "devices": devices})
            try:
                summary = work(on_result)
                self._emit(task, {"type": "done", "ok": True, **summary})
            except Exception as exc:  # noqa: BLE001 - shown to the user, not raised
                self._emit(task, {"type": "done", "ok": False, "message": f"{type(exc).__name__}: {exc}"})
            finally:
                task.finished = datetime.now()
                with self._cond:
                    self._cond.notify_all()

        threading.Thread(target=runner, name=f"web-task-{task.id}", daemon=True).start()
        return task

    def follow(self, task: WebTask, timeout: float = 600) -> Iterator[Dict[str, Any]]:
        """Yield every event of ``task`` (old ones first), waiting for new ones until it ends."""
        sent = 0
        deadline = time.monotonic() + timeout
        while True:
            with self._cond:
                while sent >= len(task.events) and not task.done and time.monotonic() < deadline:
                    self._cond.wait(timeout=1)
                new = task.events[sent:]
            for event in new:
                yield event
            sent += len(new)
            if (task.done and sent >= len(task.events)) or time.monotonic() >= deadline:
                return
