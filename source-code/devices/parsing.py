"""Small text-parsing helpers shared by the vendor classes."""

import re
import shlex
from typing import Dict, Optional, Tuple

_DURATION_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def duration_to_seconds(text: str) -> Optional[int]:
    """Convert ``1w2d3h4m5s`` or ``3h 4m 5s`` (also ``2 days, 3h``) to seconds."""
    if not text:
        return None
    # "1w2d3h", "3h 4m 5s" and "1 week, 2 days, 3 hours" all match: the unit is
    # the first letter after the number.
    parts = re.findall(r"(\d+)\s*([wdhms])", text.lower())
    if not parts:
        return None
    return sum(int(value) * _DURATION_UNITS[unit] for value, unit in parts)


def key_value_block(output: str) -> Dict[str, str]:
    """Parse ``key: value`` lines (RouterOS ``print`` and VyOS ``show version``)."""
    result: Dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key and key not in result:
            result[key] = value.strip()
    return result


def terse_line(line: str) -> Tuple[str, Dict[str, str]]:
    """Split a RouterOS ``print terse`` line into (flags, {key: value}).

    Example: ``0  R  name=ether1 type=ether mtu=1500`` -> ("R", {"name": "ether1", ...}).
    """
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError:
        tokens = line.split()
    flags = []
    comment = []
    in_comment = False
    fields: Dict[str, str] = {}
    for token in tokens:
        if token == ";;;":
            in_comment = True
        elif "=" in token:
            in_comment = False
            key, _, value = token.partition("=")
            fields[key] = value
        elif in_comment:
            comment.append(token)
        elif not fields and not token.isdigit():
            flags.append(token)
    if comment and "comment" not in fields:
        fields["comment"] = " ".join(comment)
    return "".join(flags), fields
