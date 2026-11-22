"""Configuration compliance checks (Strategy pattern, like the anomaly rules).

Each check reads the running configuration text of one device and says
whether it meets one point of the group's baseline policy. Vendor syntax is
kept in a small table per check, so adding a vendor means adding one entry.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.models import ComplianceResult, DeviceFacts

Verdict = Tuple[Optional[bool], str]  # (None = check does not apply, detail)


def normalize(config: str) -> str:
    """Join RouterOS continuation lines (``\\`` + newline + indent) so each entry is one line."""
    return re.sub(r"\\\r?\n\s*", "", config.replace("\r\n", "\n"))


class ComplianceCheck(ABC):
    """One point of the configuration policy."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def verify(self, device_type: str, config: str, expected: Dict[str, Any]) -> Verdict:
        """Return ``(passed, detail)``; ``passed`` is None when the check does not apply."""


class _PatternCheck(ComplianceCheck):
    """Passes when ``required[device_type]`` matches and ``forbidden[device_type]`` does not."""

    required: Dict[str, str] = {}
    forbidden: Dict[str, str] = {}

    def verify(self, device_type: str, config: str, expected: Dict[str, Any]) -> Verdict:
        need, avoid = self.required.get(device_type), self.forbidden.get(device_type)
        if need is None and avoid is None:
            return None, "chưa hỗ trợ hãng này"
        if need is not None and not re.search(need, config, re.MULTILINE):
            return False, "thiếu cấu hình"
        if avoid is not None and re.search(avoid, config, re.MULTILINE):
            return False, "có cấu hình không cho phép"
        return True, ""


class SshEnabledCheck(_PatternCheck):
    name, description = "ssh_enabled", "Bật SSH để quản trị"
    required = {"vyos": r"^set service ssh", "cisco_ios": r"transport input ssh"}
    forbidden = {"mikrotik_routeros": r"^set ssh .*disabled=yes"}  # RouterOS: on by default


class TelnetDisabledCheck(_PatternCheck):
    name, description = "telnet_disabled", "Tắt Telnet (không mã hóa)"
    required = {"mikrotik_routeros": r"^set telnet .*disabled=yes"}  # RouterOS: on by default
    forbidden = {"vyos": r"^set service telnet", "cisco_ios": r"transport input (all|telnet)"}


class LldpEnabledCheck(_PatternCheck):
    name, description = "lldp_enabled", "Bật LLDP để phát hiện láng giềng"
    required = {"vyos": r"^set service lldp", "cisco_ios": r"^lldp run"}
    # RouterOS discovers with LLDP by default; it fails only if the protocol list drops it.
    forbidden = {"mikrotik_routeros": r"^/ip neighbor discovery-settings\n(?:set|.*) [^\n]*protocol=(?![^\n]*lldp)"}


class LoginBannerCheck(_PatternCheck):
    name, description = "login_banner", "Có banner cảnh báo khi đăng nhập"
    required = {
        "vyos": r"^set system login banner pre-login",
        "mikrotik_routeros": r"^/system note\nset [^\n]*note=",
        "cisco_ios": r"^banner (motd|login)",
    }


class OspfRouterIdCheck(ComplianceCheck):
    """Router ID equals the one planned in ``ospf_vars.yaml``."""

    name, description = "ospf_router_id", "OSPF router-id đúng quy hoạch"
    PATTERNS = {
        "vyos": "set protocols ospf parameters router-id '?{rid}'?$",
        "mikrotik_routeros": r"router-id={rid}\b",
        "cisco_ios": r"router-id {rid}$",
    }

    def verify(self, device_type: str, config: str, expected: Dict[str, Any]) -> Verdict:
        rid = expected.get("router_id")
        pattern = self.PATTERNS.get(device_type)
        if not rid or pattern is None:
            return None, "không có router-id quy hoạch"
        found = re.search(pattern.format(rid=re.escape(str(rid))), config, re.MULTILINE)
        return (True, "") if found else (False, f"chưa có router-id {rid}")


DEFAULT_CHECKS: Sequence[ComplianceCheck] = (
    SshEnabledCheck(), TelnetDisabledCheck(), LldpEnabledCheck(), LoginBannerCheck(), OspfRouterIdCheck(),
)


class ComplianceChecker:
    """Runs a list of checks against device configurations."""

    def __init__(self, checks: Sequence[ComplianceCheck] = DEFAULT_CHECKS,
                 expected: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self._checks = list(checks)
        self._expected = expected or {}

    def evaluate(self, device: str, device_type: str, config: str) -> List[ComplianceResult]:
        text = normalize(config)
        results = []
        for check in self._checks:
            passed, detail = check.verify(device_type, text, self._expected.get(device, {}))
            if passed is not None:
                results.append(ComplianceResult(check.name, check.description, passed, detail))
        return results

    @staticmethod
    def overall_percent(facts: Sequence[DeviceFacts]) -> Optional[float]:
        """Passed checks / all checks over several devices."""
        results = [c for f in facts for c in f.compliance]
        if not results:
            return None
        return round(100 * sum(c.passed for c in results) / len(results), 1)
