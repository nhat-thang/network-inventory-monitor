"""Run a task again and again at a fixed interval (scheduled backups)."""

import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger("netmon")


class PeriodicRunner:
    """Call ``task()`` every ``interval_minutes`` until ``times`` runs are done or ``stop()``.

    ``times=None`` means run until stopped (Ctrl+C on the command line).
    """

    def __init__(self, task: Callable[[], object], interval_minutes: float,
                 times: Optional[int] = None) -> None:
        if interval_minutes <= 0:
            raise ValueError("interval_minutes must be > 0")
        if times is not None and times < 1:
            raise ValueError("times must be >= 1")
        self._task = task
        self._interval = interval_minutes * 60
        self._times = times
        self._stop = threading.Event()
        self._runs = 0

    @property
    def runs(self) -> int:
        """How many times the task has run."""
        return self._runs

    def stop(self) -> None:
        """Ask the loop to finish after the current run."""
        self._stop.set()

    def run(self) -> None:
        """Blocking loop: run now, then wait ``interval`` between runs."""
        while not self._stop.is_set():
            self._runs += 1
            logger.info("scheduled run %d started", self._runs)
            try:
                self._task()
            except Exception as exc:  # noqa: BLE001 - one failed run must not end the schedule
                logger.error("scheduled run %d failed: %s", self._runs, exc)
            if self._times is not None and self._runs >= self._times:
                break
            next_run = datetime.now() + timedelta(seconds=self._interval)
            logger.info("next scheduled run at %s", next_run.strftime("%H:%M:%S"))
            self._stop.wait(self._interval)
