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
Interactive mode proxy module.

Mediates I/O between user code and judge code running in separate sandboxes.
Implements asymmetric I/O filtering:
- Judge → User: transparent passthrough (no filtering)
- User → Judge: filtered through firewall rules (character whitelist, format validation, etc.)
"""

import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)


class ProxyErrorClass(Enum):
    """Error classifications for proxy execution."""
    PASS = "PASS"
    FAULT = "FAULT"
    JUDGE_RUNTIME_ERROR = "JUDGE_RUNTIME_ERROR"
    USER_RUNTIME_ERROR = "USER_RUNTIME_ERROR"
    JUDGE_COMPILATION_ERROR = "JUDGE_COMPILATION_ERROR"
    USER_COMPILATION_ERROR = "USER_COMPILATION_ERROR"
    JUDGE_TIMEOUT = "JUDGE_TIMEOUT"
    USER_TIMEOUT = "USER_TIMEOUT"
    FIREWALL_VIOLATION = "FIREWALL_VIOLATION"
    JUDGE_CRASHED = "JUDGE_CRASHED"
    USER_CRASHED = "USER_CRASHED"
    PROXY_COMMUNICATION_ERROR = "PROXY_COMMUNICATION_ERROR"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


class FirewallViolationType(Enum):
    """Types of firewall rule violations."""
    INVALID_CHARACTER = "INVALID_CHARACTER"
    LINE_TOO_LONG = "LINE_TOO_LONG"
    TOTAL_BYTES_EXCEEDED = "TOTAL_BYTES_EXCEEDED"
    FORMAT_VALIDATION_FAILED = "FORMAT_VALIDATION_FAILED"


@dataclass
class FirewallRules:
    """Firewall rules for user → judge I/O filtering."""
    allowed_chars: Optional[str] = None  # regex pattern (e.g., r'[a-zA-Z0-9\s\n]')
    max_line_length: Optional[int] = None  # max bytes per line
    max_total_bytes: Optional[int] = None  # max total bytes user can send
    format_rules: List[str] = field(default_factory=list)  # custom validator names
    violation_action: str = "STOP"  # "STOP" or "WARN"
    custom_validators: Dict[str, Callable[[bytes], bool]] = field(default_factory=dict)

    def compile(self):
        """Pre-compile regex patterns for efficiency."""
        if self.allowed_chars:
            try:
                self.allowed_chars = re.compile(self.allowed_chars)
            except re.error as e:
                raise ValueError(f"Invalid allowed_chars regex: {e}")

    def validate_data(self, data: bytes, total_sent: int) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate user input against firewall rules.
        
        Returns:
            (is_valid, violation_details)
            violation_details is None if valid, else contains violation info
        """
        if not data:
            return True, None

        # Check character whitelist
        if isinstance(self.allowed_chars, re.Pattern):
            for i, byte_val in enumerate(data):
                    try:
                        char = chr(byte_val)
                    except (ValueError, OverflowError):
                        char = f"\\x{byte_val:02x}"
                
                    if not self.allowed_chars.match(char):
                        return False, {
                            'violation_type': FirewallViolationType.INVALID_CHARACTER.value,
                            'position': i,
                            'character': char,
                            'byte': byte_val,
                        }

        # Check line length
        if self.max_line_length:
            lines = data.split(b'\n')
            for line_idx, line in enumerate(lines):
                if len(line) > self.max_line_length:
                    return False, {
                        'violation_type': FirewallViolationType.LINE_TOO_LONG.value,
                        'line_index': line_idx,
                        'line_length': len(line),
                        'max_allowed': self.max_line_length,
                    }

        # Check total bytes
        new_total = total_sent + len(data)
        if self.max_total_bytes and new_total > self.max_total_bytes:
            return False, {
                'violation_type': FirewallViolationType.TOTAL_BYTES_EXCEEDED.value,
                'bytes_sent': total_sent,
                'bytes_attempted': len(data),
                'total': new_total,
                'max_allowed': self.max_total_bytes,
            }

        # Custom format validators
        for validator_name in self.format_rules:
            if validator_name in self.custom_validators:
                validator = self.custom_validators[validator_name]
                if not validator(data):
                    return False, {
                        'violation_type': FirewallViolationType.FORMAT_VALIDATION_FAILED.value,
                        'validator': validator_name,
                    }

        return True, None


@dataclass
class IOTranscript:
    """Transcript of I/O exchanges for verbose mode."""
    rounds: List[Dict[str, Any]] = field(default_factory=list)

    def add_round(self, round_num: int, user_input: bytes, judge_output: bytes, 
                  firewall_violation: Optional[Dict] = None):
        """Record a round of I/O exchange."""
        self.rounds.append({
            'round': round_num,
            'user_input': user_input.decode('utf-8', errors='replace'),
            'judge_output': judge_output.decode('utf-8', errors='replace'),
            'firewall_violation': firewall_violation,
        })


@dataclass
class ProxyProcessInfo:
    """Information about a process in proxy execution."""
    proc: asyncio.subprocess.Process
    name: str  # "user" or "judge"
    stdin_task: Optional[asyncio.Task] = None
    stdout_task: Optional[asyncio.Task] = None
    stderr_data: bytes = field(default_factory=bytes)
    stdout_data: bytes = field(default_factory=bytes)
    stderr_lines: List[str] = field(default_factory=list)
    total_bytes_read: int = 0


@dataclass
class ProxyResult:
    """Result of interactive proxy execution."""
    verdict: ProxyErrorClass
    user_crashed: bool = False
    judge_crashed: bool = False
    user_exit_code: Optional[int] = None
    judge_exit_code: Optional[int] = None
    user_signal: Optional[int] = None
    judge_signal: Optional[int] = None
    firewall_violation: Optional[Dict[str, Any]] = None
    judge_output: bytes = field(default_factory=bytes)
    user_stderr: bytes = field(default_factory=bytes)
    judge_stderr: bytes = field(default_factory=bytes)
    total_user_bytes_sent: int = 0
    total_judge_bytes_sent: int = 0
    io_transcript: Optional[IOTranscript] = None
    resource_limit_exceeded: Optional[str] = None  # "user_time", "judge_memory", etc.
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        transcript_data = None
        if self.io_transcript:
            transcript_data = self.io_transcript.rounds

        return {
            'verdict': self.verdict.value,
            'user_crashed': self.user_crashed,
            'judge_crashed': self.judge_crashed,
            'user_exit_code': self.user_exit_code,
            'judge_exit_code': self.judge_exit_code,
            'user_signal': self.user_signal,
            'judge_signal': self.judge_signal,
            'firewall_violation': self.firewall_violation,
            'judge_output': self.judge_output.decode('utf-8', errors='replace'),
            'user_stderr': self.user_stderr.decode('utf-8', errors='replace'),
            'judge_stderr': self.judge_stderr.decode('utf-8', errors='replace'),
            'total_user_bytes_sent': self.total_user_bytes_sent,
            'total_judge_bytes_sent': self.total_judge_bytes_sent,
            'io_transcript': transcript_data,
            'resource_limit_exceeded': self.resource_limit_exceeded,
            'error_message': self.error_message,
        }


class InteractiveProxy:
    """
    Manages bidirectional I/O between user and judge processes.
    
    Architecture:
    - Judge → User: transparent passthrough (no filtering)
    - User → Judge: filtered through firewall rules
    """

    def __init__(self, firewall_rules: Optional[FirewallRules] = None,
                 record_transcript: bool = False, timeout: float = 30.0,
                 judge_fault_exitcode: Optional[int] = None):
        """
        Initialize proxy.
        
        Args:
            firewall_rules: Optional firewall rules for user→judge filtering
            record_transcript: If True, record all I/O for verbose output
            timeout: Overall timeout for proxy execution (seconds)
            judge_fault_exitcode: Judge exit code that means wrong answer (FAULT)
        """
        self.firewall_rules = firewall_rules or FirewallRules()
        self.firewall_rules.compile()
        self.record_transcript = record_transcript
        self.timeout = timeout
        self.transcript = IOTranscript() if record_transcript else None
        self.user_proc: Optional[ProxyProcessInfo] = None
        self.judge_proc: Optional[ProxyProcessInfo] = None
        self.total_user_bytes_sent = 0
        self.total_judge_bytes_sent = 0
        self.judge_output_buffer = bytearray()
        self.judge_fault_exitcode = judge_fault_exitcode

    async def run(self, user_cmd: List[str], judge_cmd: List[str],
                  user_env: Optional[Dict[str, str]] = None,
                  judge_env: Optional[Dict[str, str]] = None) -> ProxyResult:
        """
        Run user and judge processes with I/O mediation.
        
        Args:
            user_cmd: Command to execute user code
            judge_cmd: Command to execute judge code
            user_env: Environment variables for user process
            judge_env: Environment variables for judge process
            
        Returns:
            ProxyResult with verdict and details
        """
        try:
            # Spawn both processes
            self.user_proc = await self._spawn_process(user_cmd, "user", user_env)
            self.judge_proc = await self._spawn_process(judge_cmd, "judge", judge_env)

            # Set up I/O forwarding tasks
            forward_task = asyncio.create_task(self._forward_io())
            
            try:
                await asyncio.wait_for(forward_task, timeout=self.timeout)
            except asyncio.TimeoutError:
                return self._handle_timeout()

            # Wait for both processes to finish
            await asyncio.wait_for(
                asyncio.gather(
                    self.user_proc.proc.wait(),
                    self.judge_proc.proc.wait()
                ),
                timeout=5.0
            )

            return self._build_result()

        except Exception as e:
            logger.exception(f"Proxy execution error: {e}")
            return ProxyResult(
                verdict=ProxyErrorClass.PROXY_COMMUNICATION_ERROR,
                error_message=str(e)
            )
        finally:
            await self._cleanup()

    async def _spawn_process(self, cmd: List[str], name: str,
                            env: Optional[Dict[str, str]] = None) -> ProxyProcessInfo:
        """Spawn a subprocess with PIPE I/O."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            return ProxyProcessInfo(proc=proc, name=name)
        except Exception as e:
            logger.error(f"Failed to spawn {name} process: {e}")
            raise

    async def _forward_io(self):
        """Forward I/O between user and judge processes concurrently."""
        try:
            # Create concurrent tasks for reading from both processes
            user_reader = asyncio.create_task(self._read_process_stream(self.user_proc))
            judge_reader = asyncio.create_task(self._read_process_stream(self.judge_proc))
            
            # Wait for both readers to complete (END OF STREAM)
            await asyncio.gather(user_reader, judge_reader, return_exceptions=True)
            
            # Now wait for both processes to exit
            await asyncio.gather(
                self.user_proc.proc.wait(),
                self.judge_proc.proc.wait(),
                return_exceptions=True
            )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"I/O forwarding error: {e}")

    async def _read_process_stream(self, proc_info: ProxyProcessInfo):
        """Read all available data from a process and forward appropriately."""
        try:
            while True:
                if proc_info.proc.stdout.at_eof():
                    break

                try:
                    data = await asyncio.wait_for(
                        proc_info.proc.stdout.read(4096),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # No data yet: keep waiting until global proxy timeout
                    # or process termination.
                    if proc_info.proc.returncode is not None:
                        break
                    continue
                
                if not data:
                    break
                
                if proc_info.name == "judge":
                    # Judge → User: transparent passthrough
                    self.judge_output_buffer.extend(data)
                    self._write_to_process(self.user_proc, data)
                    self.total_judge_bytes_sent += len(data)
                elif proc_info.name == "user":
                    # User → Judge: apply firewall rules
                    is_valid, violation = self.firewall_rules.validate_data(
                        data, self.total_user_bytes_sent
                    )
                    
                    if not is_valid:
                        logger.warning(f"Firewall violation: {violation}")
                        self._firewall_violation = violation
                        
                        if self.firewall_rules.violation_action == "STOP":
                            # Stop execution
                            self.user_proc.proc.terminate()
                            self.judge_proc.proc.terminate()
                            return
                        # else WARN: continue despite violation
                    
                    self._write_to_process(self.judge_proc, data)
                    self.total_user_bytes_sent += len(data)

        except Exception as e:
            logger.warning(f"Error reading from {proc_info.name}: {e}")

    def _write_to_process(self, proc_info: ProxyProcessInfo, data: bytes):
        """Write data to process stdin."""
        if proc_info.proc.stdin and not proc_info.proc.stdin.is_closing():
            try:
                proc_info.proc.stdin.write(data)
            except Exception as e:
                logger.warning(f"Error writing to {proc_info.name}: {e}")

    async def _cleanup(self):
        """Clean up processes and resources."""
        for proc_info in [self.user_proc, self.judge_proc]:
            if proc_info and proc_info.proc:
                if proc_info.proc.stdin and not proc_info.proc.stdin.is_closing():
                    proc_info.proc.stdin.close()

                if proc_info.proc.returncode is not None:
                    continue

                try:
                    proc_info.proc.terminate()
                    await asyncio.wait_for(proc_info.proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    try:
                        proc_info.proc.kill()
                        await proc_info.proc.wait()
                    except ProcessLookupError:
                        pass
                except ProcessLookupError:
                    pass

    def _handle_timeout(self) -> ProxyResult:
        """Handle proxy timeout."""
        # Determine which process timed out (or both)
        user_timed_out = self.user_proc and self.user_proc.proc.returncode is None
        judge_timed_out = self.judge_proc and self.judge_proc.proc.returncode is None

        verdict = ProxyErrorClass.USER_TIMEOUT if user_timed_out else ProxyErrorClass.JUDGE_TIMEOUT

        result = ProxyResult(
            verdict=verdict,
            user_exit_code=self.user_proc.proc.returncode if self.user_proc else None,
            judge_exit_code=self.judge_proc.proc.returncode if self.judge_proc else None,
            total_user_bytes_sent=self.total_user_bytes_sent,
            total_judge_bytes_sent=self.total_judge_bytes_sent,
            error_message=f"Timeout after {self.timeout}s"
        )

        return result

    def _build_result(self) -> ProxyResult:
        """Build final result from process state."""
        # Determine verdict based on exit codes and crashes
        user_exit_code = self.user_proc.proc.returncode if self.user_proc else None
        judge_exit_code = self.judge_proc.proc.returncode if self.judge_proc else None

        # Check for crashes (negative exit code = signal)
        user_crashed = user_exit_code is not None and user_exit_code < 0
        judge_crashed = judge_exit_code is not None and judge_exit_code < 0

        verdict = ProxyErrorClass.PASS

        if hasattr(self, '_firewall_violation') and self._firewall_violation:
            verdict = ProxyErrorClass.FIREWALL_VIOLATION
        elif judge_crashed:
            verdict = ProxyErrorClass.JUDGE_CRASHED
        elif user_crashed:
            verdict = ProxyErrorClass.USER_CRASHED
        elif (self.judge_fault_exitcode is not None and
              judge_exit_code == self.judge_fault_exitcode):
            verdict = ProxyErrorClass.FAULT
        elif judge_exit_code != 0:
            verdict = ProxyErrorClass.JUDGE_RUNTIME_ERROR
        elif user_exit_code != 0:
            verdict = ProxyErrorClass.USER_RUNTIME_ERROR

        result = ProxyResult(
            verdict=verdict,
            user_crashed=user_crashed,
            judge_crashed=judge_crashed,
            user_exit_code=user_exit_code,
            judge_exit_code=judge_exit_code,
            user_signal=abs(user_exit_code) if user_crashed else None,
            judge_signal=abs(judge_exit_code) if judge_crashed else None,
            firewall_violation=getattr(self, '_firewall_violation', None),
            judge_output=bytes(self.judge_output_buffer),
            total_user_bytes_sent=self.total_user_bytes_sent,
            total_judge_bytes_sent=self.total_judge_bytes_sent,
            io_transcript=self.transcript,
        )

        return result
