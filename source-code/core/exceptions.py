"""Custom exception hierarchy.

Library-specific errors (Netmiko, paramiko, socket) are translated into these
classes inside ``NetworkDevice`` so the rest of the program never depends on
the underlying library.
"""


class NetworkAutomationError(Exception):
    """Base class for every error raised by this project."""


class DeviceConnectionError(NetworkAutomationError):
    """The device could not be reached or the session dropped."""


class DeviceAuthenticationError(DeviceConnectionError):
    """Wrong username, password or enable secret."""


class DeviceTimeoutError(DeviceConnectionError):
    """The device did not answer in time."""


class UnsupportedDeviceError(NetworkAutomationError):
    """No device class is registered for the requested ``device_type``."""


class ConfigPushError(NetworkAutomationError):
    """Applying configuration to a device failed."""
