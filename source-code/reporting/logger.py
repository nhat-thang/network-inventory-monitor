"""Application-wide logger (Singleton pattern).

Every module logs through ``logging.getLogger("netmon")``; ``AppLogger``
configures that logger exactly once, however many times it is instantiated.
"""

import getpass
import logging
from pathlib import Path
from typing import Optional


class _OperatorFilter(logging.Filter):
    """Add the OS user running the program to every record (who did what)."""

    def __init__(self) -> None:
        super().__init__()
        try:
            self._operator = getpass.getuser()
        except Exception:  # noqa: BLE001 - no login name in some environments
            self._operator = "unknown"

    def filter(self, record: logging.LogRecord) -> bool:
        record.operator = self._operator
        return True


class AppLogger:
    """Single shared configuration for the ``netmon`` logger."""

    _instance: Optional["AppLogger"] = None
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | user=%(operator)s | %(threadName)s | %(message)s"

    def __new__(cls, log_dir: Path = Path("output/logs"), level: int = logging.INFO) -> "AppLogger":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._configure(Path(log_dir), level)
            cls._instance = instance
        return cls._instance

    def _configure(self, log_dir: Path, level: int) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("netmon")
        self._logger.setLevel(level)
        operator_filter = _OperatorFilter()
        formatter = logging.Formatter(self.LOG_FORMAT)
        file_handler = logging.FileHandler(log_dir / "automation.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(operator_filter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(operator_filter)
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

    @property
    def logger(self) -> logging.Logger:
        """The configured ``netmon`` logger."""
        return self._logger
