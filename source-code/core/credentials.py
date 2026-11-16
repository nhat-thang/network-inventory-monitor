"""Credential handling (encapsulation).

Secrets live in private attributes, are exposed through read-only properties
and never appear in ``repr``/``str`` output or in log lines.
"""

import os
from typing import Optional

from dotenv import load_dotenv


class Credentials:
    """Username, password and optional enable secret for a device."""

    def __init__(self, username: str, password: str, secret: Optional[str] = None) -> None:
        if not username or not password:
            raise ValueError("username and password must not be empty")
        self.__username = username
        self.__password = password
        self.__secret = secret

    @property
    def username(self) -> str:
        """Login name."""
        return self.__username

    @property
    def password(self) -> str:
        """Login password (never logged)."""
        return self.__password

    @property
    def secret(self) -> Optional[str]:
        """Enable secret, if the platform needs one."""
        return self.__secret

    def __repr__(self) -> str:
        return f"Credentials(username={self.__username!r}, password='***')"

    __str__ = __repr__

    @classmethod
    def from_env(cls, prefix: str = "NET") -> "Credentials":
        """Build credentials from ``<PREFIX>_USERNAME`` / ``_PASSWORD`` / ``_SECRET``.

        Values are read from environment variables, after loading a ``.env``
        file if one exists in the working directory.
        """
        load_dotenv()
        username = os.getenv(f"{prefix}_USERNAME", "")
        password = os.getenv(f"{prefix}_PASSWORD", "")
        if not username or not password:
            raise ValueError(
                f"Missing {prefix}_USERNAME or {prefix}_PASSWORD; copy .env.example to .env"
            )
        return cls(username, password, os.getenv(f"{prefix}_SECRET") or None)
