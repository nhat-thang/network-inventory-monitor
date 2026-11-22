"""Compliance checks on real lab configs (before baseline) and on configs after the baseline template."""

from pathlib import Path

from core.models import DeviceFacts
from monitoring.compliance import ComplianceChecker, LldpEnabledCheck, normalize

SAMPLES = Path(__file__).parent / "samples"
EXPECTED = {"R1": {"router_id": "1.1.1.1"}, "VY1": {"router_id": "3.3.3.3"}}

MIKROTIK_AFTER = """/ip neighbor discovery-settings
set discover-interface-list=all
/ip service
set telnet disabled=yes
/routing ospf instance
add disabled=no name=default-v2 router-id=1.1.1.1
/system note
set note="Thiet bi thuoc lab Nhom 1 - chi nguoi co tham quyen \\
    moi duoc truy cap"
"""

VYOS_AFTER = """set protocols ospf parameters router-id '3.3.3.3'
set service lldp interface all
set service ssh port '22'
set system login banner pre-login 'Thiet bi thuoc lab Nhom 1'
"""


def _result(results):
    return {r.check: r.passed for r in results}


def test_real_configs_before_baseline():
    checker = ComplianceChecker(expected=EXPECTED)
    mt = _result(checker.evaluate("R1", "mikrotik_routeros", (SAMPLES / "mikrotik/export.txt").read_text()))
    assert mt == {"ssh_enabled": True, "telnet_disabled": False, "lldp_enabled": True,
                  "login_banner": False, "ospf_router_id": False}
    vy = _result(checker.evaluate("VY1", "vyos",
                                  (SAMPLES / "vyos/show_configuration_commands.txt").read_text()))
    assert vy == {"ssh_enabled": True, "telnet_disabled": True, "lldp_enabled": False,
                  "login_banner": False, "ospf_router_id": False}


def test_configs_after_baseline_and_ospf_are_compliant():
    checker = ComplianceChecker(expected=EXPECTED)
    for name, device_type, config in [("R1", "mikrotik_routeros", MIKROTIK_AFTER), ("VY1", "vyos", VYOS_AFTER)]:
        results = checker.evaluate(name, device_type, config)
        assert len(results) == 5 and all(r.passed for r in results), (name, results)


def test_skips_checks_that_do_not_apply_and_overall_percent():
    checker = ComplianceChecker()  # no planned router IDs
    results = checker.evaluate("X", "vyos", VYOS_AFTER)
    assert "ospf_router_id" not in _result(results) and len(results) == 4
    a, b = DeviceFacts(device="A", vendor="v"), DeviceFacts(device="B", vendor="v")
    a.compliance, b.compliance = results, checker.evaluate("B", "vyos", "set service ssh")
    assert b.compliance_percent == 50.0 and ComplianceChecker.overall_percent([a, b]) == 75.0
    assert DeviceFacts.from_dict(b.to_dict()).compliance == b.compliance


def test_mikrotik_lldp_removed_and_line_continuation():
    text = normalize("/ip neighbor discovery-settings\nset protocol=cdp,mndp\n")
    assert LldpEnabledCheck().verify("mikrotik_routeros", text, {})[0] is False
    assert normalize("set note=\"a \\\n    b\"") == 'set note="a b"'
