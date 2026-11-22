"""Application services shared by the CLI and the web interface."""

from services.network_service import NetworkService, ScanResult

__all__ = ["NetworkService", "ScanResult"]
