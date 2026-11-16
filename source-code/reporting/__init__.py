"""Logging (Singleton) and report generation."""

from reporting.html_report import HtmlReport
from reporting.logger import AppLogger

__all__ = ["AppLogger", "HtmlReport"]
