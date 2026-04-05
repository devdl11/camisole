# This file is part of Camisole.
#
# Copyright (c) 2016 Antoine Pietri <antoine.pietri@prologin.org>
# Copyright (c) 2016 Alexandre Macabies <alexandre.macabies@prologin.org>
# Copyright (c) 2016 Association Prologin <info@prologin.org>
#
# Camisole is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Prologin-SADM is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Prologin-SADM.  If not, see <http://www.gnu.org/licenses/>.

"""
Tests for interactive judge execution mode with proxy.
"""

import sys

import pytest
from camisole.proxy import (
    InteractiveProxy, FirewallRules, ProxyErrorClass, 
    FirewallViolationType, ProxyResult
)


def test_proxy_firewall_allowed_chars():
    """Test that firewall correctly validates allowed characters."""
    rules = FirewallRules(allowed_chars=r'[a-z0-9\n]')
    rules.compile()  # compile regex patterns before calling validate_data
    
    # Valid input
    valid, violation = rules.validate_data(b'hello\n', 0)
    assert valid
    assert violation is None
    
    # Invalid input (uppercase)
    valid, violation = rules.validate_data(b'Hello', 0)
    assert not valid
    assert violation['violation_type'] == FirewallViolationType.INVALID_CHARACTER.value
    assert violation['character'] == 'H'


def test_proxy_firewall_max_line_length():
    """Test that firewall enforces max line length."""
    rules = FirewallRules(max_line_length=5)
    rules.compile()
    
    # Valid: line within limit
    valid, violation = rules.validate_data(b'hello', 0)
    assert valid
    
    # Invalid: line exceeds limit
    valid, violation = rules.validate_data(b'hello world', 0)
    assert not valid
    assert violation['violation_type'] == FirewallViolationType.LINE_TOO_LONG.value


def test_proxy_firewall_max_total_bytes():
    """Test that firewall enforces max total bytes limit."""
    rules = FirewallRules(max_total_bytes=10)
    rules.compile()
    
    # First chunk
    valid, violation = rules.validate_data(b'hello', 0)
    assert valid
    
    # Second chunk within limit
    valid, violation = rules.validate_data(b'world', 5)
    assert valid
    
    # Third chunk exceeds limit
    valid, violation = rules.validate_data(b'!', 10)
    assert not valid
    assert violation['violation_type'] == FirewallViolationType.TOTAL_BYTES_EXCEEDED.value


@pytest.mark.asyncio
async def test_proxy_simple_echo():
    """Test simple echo: user sends 'hello', judge echoes it back."""
    proxy = InteractiveProxy(timeout=5.0)
    
    # Simple echo program: reads line and prints it
    user_cmd = ['/bin/echo', 'hello']
    judge_cmd = ['/bin/cat']  # cat reads stdin and prints to stdout
    
    result = await proxy.run(user_cmd, judge_cmd)
    
    # Should succeed (both exit with 0)
    assert result.verdict == ProxyErrorClass.PASS
    assert result.user_exit_code == 0
    assert result.judge_exit_code == 0


@pytest.mark.asyncio
async def test_proxy_firewall_violation_stop():
    """Test that firewall violation stops execution."""
    rules = FirewallRules(
        allowed_chars=r'[a-z\n]',
        violation_action='STOP'
    )
    proxy = InteractiveProxy(firewall_rules=rules, timeout=5.0)
    
    # User tries to send uppercase (violates firewall)
    user_cmd = ['/bin/echo', 'HELLO']  # uppercase not allowed
    judge_cmd = ['/bin/cat']
    
    result = await proxy.run(user_cmd, judge_cmd)
    
    # Should report firewall violation
    assert result.verdict == ProxyErrorClass.FIREWALL_VIOLATION
    assert result.firewall_violation is not None


@pytest.mark.asyncio
async def test_proxy_user_timeout():
    """Test timeout when user process doesn't produce output."""
    proxy = InteractiveProxy(timeout=1.0)
    
    # sleep command will hang
    user_cmd = ['/bin/sleep', '5']
    judge_cmd = ['/bin/cat']
    
    result = await proxy.run(user_cmd, judge_cmd)
    
    # Should timeout
    assert result.verdict == ProxyErrorClass.USER_TIMEOUT


@pytest.mark.asyncio
async def test_proxy_judge_timeout():
    """Test timeout when judge process doesn't produce output."""
    proxy = InteractiveProxy(timeout=1.0)
    
    user_cmd = ['/bin/echo', 'hello']
    judge_cmd = ['/bin/sleep', '5']  # judge hangs
    
    result = await proxy.run(user_cmd, judge_cmd)
    
    # Should timeout (judge not responding)
    assert result.verdict == ProxyErrorClass.JUDGE_TIMEOUT


@pytest.mark.asyncio
async def test_proxy_user_runtime_error():
    """Test detection of user runtime error."""
    proxy = InteractiveProxy(timeout=5.0)
    
    # Command that exits with error
    user_cmd = ['/bin/false']  # exits with code 1
    judge_cmd = ['/bin/true']
    
    result = await proxy.run(user_cmd, judge_cmd)
    
    assert result.verdict == ProxyErrorClass.USER_RUNTIME_ERROR
    assert result.user_exit_code != 0


@pytest.mark.asyncio
async def test_proxy_judge_runtime_error():
    """Test detection of judge runtime error."""
    proxy = InteractiveProxy(timeout=5.0)
    
    user_cmd = ['/bin/true']
    judge_cmd = ['/bin/false']  # exits with error
    
    result = await proxy.run(user_cmd, judge_cmd)
    
    assert result.verdict == ProxyErrorClass.JUDGE_RUNTIME_ERROR
    assert result.judge_exit_code != 0


@pytest.mark.asyncio
async def test_proxy_initial_stdin_user():
    """Initial stdin for user process is delivered before forwarding loop."""
    proxy = InteractiveProxy(timeout=5.0)

    user_cmd = [
        sys.executable, '-c',
        (
            'import sys; '
            'line = sys.stdin.readline(); '
            'sys.exit(0 if line == "seed-user\\n" else 1)'
        )
    ]
    judge_cmd = ['/bin/true']

    result = await proxy.run(
        user_cmd,
        judge_cmd,
        user_initial_stdin=b'seed-user\n',
    )

    assert result.verdict == ProxyErrorClass.PASS
    assert result.user_exit_code == 0
    assert result.judge_exit_code == 0


@pytest.mark.asyncio
async def test_proxy_initial_stdin_judge():
    """Initial stdin for judge process is delivered before forwarding loop."""
    proxy = InteractiveProxy(timeout=5.0)

    user_cmd = ['/bin/true']
    judge_cmd = [
        sys.executable, '-c',
        (
            'import sys; '
            'line = sys.stdin.readline(); '
            'sys.exit(0 if line == "seed-judge\\n" else 1)'
        )
    ]

    result = await proxy.run(
        user_cmd,
        judge_cmd,
        judge_initial_stdin=b'seed-judge\n',
    )

    assert result.verdict == ProxyErrorClass.PASS
    assert result.user_exit_code == 0
    assert result.judge_exit_code == 0


@pytest.mark.asyncio
async def test_proxy_result_to_dict():
    """Test that ProxyResult converts to JSON-serializable dict."""
    result = ProxyResult(
        verdict=ProxyErrorClass.PASS,
        user_exit_code=0,
        judge_exit_code=0,
        judge_output=b'response',
    )
    
    result_dict = result.to_dict()
    
    assert isinstance(result_dict, dict)
    assert result_dict['verdict'] == 'PASS'
    assert result_dict['user_exit_code'] == 0
    assert result_dict['judge_exit_code'] == 0


def test_firewall_rules_compile():
    """Test that firewall rules compile regex patterns."""
    rules = FirewallRules(allowed_chars=r'[a-z]+')
    rules.compile()
    
    # Should have compiled regex
    assert hasattr(rules.allowed_chars, 'match')


def test_firewall_invalid_regex():
    """Test that invalid regex raises error."""
    rules = FirewallRules(allowed_chars='[invalid')
    
    with pytest.raises(ValueError, match='Invalid allowed_chars regex'):
        rules.compile()


def test_proxy_result_bytes_decode():
    """Test that ProxyResult safely decodes binary data."""
    result = ProxyResult(
        verdict=ProxyErrorClass.PASS,
        judge_output=b'Hello \xff\xfe World',  # contains invalid UTF-8
    )
    
    result_dict = result.to_dict()
    
    # Should handle invalid UTF-8 gracefully
    assert isinstance(result_dict['judge_output'], str)


@pytest.mark.asyncio
async def test_proxy_concurrent_io():
    """Test proxy handles concurrent I/O from both processes."""
    # This is a more complex test that would need:
    # - Two processes that interactively exchange messages
    # - Verification that exchanges happen correctly
    # Skipping for now as it requires more complex setup
    pass
