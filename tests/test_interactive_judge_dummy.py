from pathlib import Path
import asyncio
import sys

import pytest

from camisole.proxy import FirewallRules, InteractiveProxy, ProxyErrorClass


DUMMY_DIR = Path(__file__).parent / "dummy"


def test_interactive_proxy_dummy_pass():
    """User sends 'hello', judge reads one line and returns PASS."""
    user_cmd = [sys.executable, str(DUMMY_DIR / "interactive_user_ok.py")]
    judge_cmd = [sys.executable, str(DUMMY_DIR / "interactive_judge_line.py")]

    proxy = InteractiveProxy(timeout=5.0, judge_fault_exitcode=42)
    result = asyncio.run(proxy.run(user_cmd, judge_cmd))

    assert result.verdict == ProxyErrorClass.PASS
    assert result.user_exit_code == 0
    assert result.judge_exit_code == 0


def test_interactive_proxy_dummy_firewall_violation():
    """User sends uppercase data, firewall blocks before judge consumes it."""
    user_cmd = [sys.executable, str(DUMMY_DIR / "interactive_user_bad.py")]
    judge_cmd = [sys.executable, str(DUMMY_DIR / "interactive_judge_line.py")]

    rules = FirewallRules(
        allowed_chars=r"[a-z\n]",
        violation_action="STOP",
    )

    proxy = InteractiveProxy(firewall_rules=rules, timeout=5.0)
    result = asyncio.run(proxy.run(user_cmd, judge_cmd))

    assert result.verdict == ProxyErrorClass.FIREWALL_VIOLATION
    assert result.firewall_violation is not None
    assert result.firewall_violation["violation_type"] == "INVALID_CHARACTER"


def test_interactive_proxy_dummy_fault_when_judge_exits_custom_code():
    """If firewall allows HELLO, judge should exit with custom WA code -> FAULT verdict."""
    user_cmd = [sys.executable, str(DUMMY_DIR / "interactive_user_bad.py")]
    judge_cmd = [sys.executable, str(DUMMY_DIR / "interactive_judge_line.py")]

    rules = FirewallRules(
        allowed_chars=r"[A-Z\n]",
        violation_action="STOP",
    )

    proxy = InteractiveProxy(
        firewall_rules=rules,
        timeout=5.0,
        judge_fault_exitcode=42,
    )
    result = asyncio.run(proxy.run(user_cmd, judge_cmd))

    assert result.verdict == ProxyErrorClass.FAULT
    assert result.judge_exit_code == 42


def test_interactive_proxy_dummy_fault_no_firewall():
    """Without firewall, judge receives correct input and exits with fault code -> FAULT verdict.

    Regression test: the real judge program exit code (42) must be propagated even
    when the program exits non-zero.  Previously, in the isolate-backed path the
    exit code was read from the isolate *wrapper* (which returns 1 for any non-zero
    child exit) rather than from the sandbox metadata, so the fault-exit-code check
    always failed and the verdict was incorrectly JUDGE_RUNTIME_ERROR.
    """
    # User sends "HELLO" (not "hello"), so judge will exit with 42 (fault code).
    user_cmd = [sys.executable, str(DUMMY_DIR / "interactive_user_bad.py")]
    judge_cmd = [sys.executable, str(DUMMY_DIR / "interactive_judge_line.py")]

    proxy = InteractiveProxy(
        timeout=5.0,
        judge_fault_exitcode=42,
    )
    result = asyncio.run(proxy.run(user_cmd, judge_cmd))

    assert result.verdict == ProxyErrorClass.FAULT
    assert result.judge_exit_code == 42
