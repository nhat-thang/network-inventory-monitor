"""Run one task on many devices concurrently.

A failure on one device is caught and reported in its ``TaskResult``; it never
stops the tasks running on the other devices.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, List, TypeVar

from core.models import TaskResult
from devices.base import NetworkDevice

logger = logging.getLogger("netmon")

T = TypeVar("T")


class ConnectionManager:
    """Thread-pool executor for per-device tasks."""

    def __init__(self, max_workers: int = 8) -> None:
        self._max_workers = max_workers

    def run(
        self,
        devices: Iterable[NetworkDevice],
        task: Callable[[NetworkDevice], T],
    ) -> List[TaskResult]:
        """Connect to each device, run ``task(device)``, then disconnect.

        Returns one ``TaskResult`` per device, in completion order.
        """
        devices = list(devices)
        results: List[TaskResult] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(self._run_one, dev, task): dev for dev in devices}
            for future in as_completed(futures):
                results.append(future.result())
        return results

    @staticmethod
    def _run_one(device: NetworkDevice, task: Callable[[NetworkDevice], T]) -> TaskResult:
        try:
            with device:
                value = task(device)
            logger.info("%s: task succeeded", device.name)
            return TaskResult(device=device.name, success=True, result=value)
        except Exception as exc:  # noqa: BLE001 - one device must not stop the others
            logger.error("%s: %s: %s", device.name, type(exc).__name__, exc)
            return TaskResult(device=device.name, success=False, error=f"{type(exc).__name__}: {exc}")
