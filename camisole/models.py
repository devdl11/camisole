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

import functools
import itertools
import logging
import os
import re
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Type

import camisole.isolate
import camisole.utils
from camisole.conf import conf


class Program:
    def __init__(self, cmd, *, 
                 opts=None, env=None,
                 version_opt='--version', version_lines=1,
                 version_regex=r'[0-9]+(\.[0-9]+)+'
                 ):

        self.cmd = camisole.utils.which(cmd)
        self.cmd_name = cmd

        self.opts = opts or []
        self.env = env or {}

        self.version_opt = version_opt
        self.version_lines = version_lines
        self.version_regex = re.compile(version_regex)

    @functools.lru_cache()
    def _version(self):
        if self.version_opt is None:  # noqa
            return None

        proc = subprocess.run([self.cmd, self.version_opt],
            stderr=subprocess.STDOUT, stdout=subprocess.PIPE
        )

        return proc.stdout.decode().strip()

    def version(self):
        if self.version_opt is None:  # noqa
            return None

        version_str = self._version()
        if version_str is None:
            return None

        res = self.version_regex.search(version_str)

        return res.group(0) if res else None

    def long_version(self):
        if self.version_opt is None:
            return None

        version_str = self.version()
        if version_str is None:
            return None

        return '\n'.join(
                version_str.split('\n')[:self.version_lines]
            )


class LangDefinition:
    name: Optional[str] = None

    source_ext: Optional[str] = None
    compiler: Optional[Program] = None
    interpreter: Optional[Program] = None
    allowed_dirs: List[str] = list()
    extra_binaries: Dict[str, Program] = dict()
    reference_source: Optional[str] = None
    executer: Optional[Type['LangExecution']] = None


    def __init_subclass__(cls, register=True, name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.name = name or cls.__name__
        
        if not register:
            return
        
        registry_name = cls.name.lower()
        
        for binary in cls.required_binaries():
            if binary is not None and not os.access(binary.cmd, os.X_OK):
                logging.info(
                        f'{cls.name}: cannot access `{binary.cmd}`, '
                                'language not loaded'
                        )
                return
        
        registered, replaced = LangExecution.register_definition(cls)

        if registered and not replaced:
            logging.info(f'{cls.name} language registered with name "{registry_name}"')
        elif registered and replaced:
            logging.info(
                f'{cls.name} language registered with name "{registry_name}", '
                        'replacing previous definition'
                )


    @classmethod
    def required_binaries(cls):
        if cls.compiler:
            yield cls.compiler

        if cls.interpreter:
            yield cls.interpreter

        yield from cls.extra_binaries.values()


    @classmethod
    def programs(cls):
        return {p.cmd_name: {'version': p.version(), 'opts': p.opts}
                for p in cls.required_binaries()}

BinaryNamedFile = tuple[str, bytes]

class LangExecution:
    opts: dict
    df: Type[LangDefinition]
    
    _registry: Dict[str, Type['LangExecution']] = {}
    _definition_registry: Dict[str, Type[LangDefinition]] = {}
    
    @classmethod
    def register_definition(cls: Type['LangExecution'], definition_cls: Type[LangDefinition]) -> tuple[bool, bool]:
        """ Registers a LangDefinition class to be used by LangExecution classes.
        Args:
            definition_cls (Type[LangDefinition]): the LangDefinition class to register
        
        Returns:
            tuple(bool, bool): (registered, overwritten)
        """

        if definition_cls.name is None:
            return False, False

        registry_name = definition_cls.name.lower()
        replaced = False

        if registry_name in cls._definition_registry:
            replaced = True

            def full_name(c):
                return f"{c.__module__}.{c.__qualname__}"

            warnings.warn(
                        f"LangExecution definition registry: name '{registry_name}' for "
                        f"{full_name(definition_cls)} overwrites "
                        f"{full_name(cls._definition_registry[registry_name])}"
                    )

        cls._definition_registry[registry_name] = definition_cls
        
        if definition_cls.executer is None:
            # Dynamically create an executer class if not defined, to avoid boilerplate for simple languages
            definition_cls.executer = type(
                    f"{definition_cls.name}Execution",
                    (cls,),
                    {}
                )

        cls._registry[registry_name] = definition_cls.executer
        definition_cls.executer.register_language(definition_cls)

        return True, replaced


    @classmethod
    def register_language(cls, language_cls: Type['LangDefinition']) -> None:
        cls.df = language_cls


    @classmethod
    def required_binaries(cls):
        yield from cls.df.required_binaries()


    def __init__(self, opts: dict):
        name = opts.get('lang', self.df.name)
        
        if name not in self._registry:
            raise ValueError(f"language {name} not found")

        self.opts = opts


    def __repr__(self):
        return "<{realname}{name}>"\
            .format(
                realname=self.df.name,
                name=f' “{self.df.name}”' 
                    if self.df.name != self.df.__class__.__name__ 
                    else ''
            )


    async def compile(self):
        if not self.df.compiler:
            raise RuntimeError("no compiler")

        # We give compilers a nice /tmp playground
        root_tmp = tempfile.TemporaryDirectory(prefix='camisole-tmp-')
        os.chmod(root_tmp.name, 0o777)
        tmparg = [f'/tmp={root_tmp.name}:rw']

        isolator = camisole.isolate.Isolator(
            self.opts.get('compile', {}),
            allowed_dirs=self.get_allowed_dirs() + tmparg)

        async with isolator:
            assert isolator.path is not None

            wd = Path(isolator.path)
            env = {'HOME': self.filter_box_prefix(str(wd))}
            source = wd / self.source_filename()
            compiled = wd / self.execute_filename()

            with source.open('wb') as sourcefile:
                sourcefile.write(
                    camisole.utils.force_bytes(self.opts.get('source', '')))

            cmd = self.compile_command(str(source), str(compiled))

            await isolator.run(cmd, env={**env, **self.df.compiler.env})

            binary = self.read_compiled(str(compiled), isolator)

            if binary is not None:
                binary = binary[1]

        root_tmp.cleanup()

        return (isolator.isolate_retcode, isolator.info, binary)


    async def execute(self, binary, opts=None):
        if opts is None:
            opts = {}

        opts = {**self.opts.get('execute', {}), **opts}
        input_data = None

        if 'stdin' in opts and opts['stdin']:
            input_data = camisole.utils.force_bytes(opts['stdin'])

        isolator = camisole.isolate.Isolator(
            opts, allowed_dirs=self.get_allowed_dirs())

        async with isolator:
            assert isolator.path is not None

            wd = isolator.path
            env = {'HOME': self.filter_box_prefix(str(wd))}
            compiled = self.write_binary(Path(wd), binary)

            env = {**env, **(self.df.interpreter.env if self.df.interpreter else {})}

            await isolator.run(
                                self.execute_command(str(compiled)),
                                env=env, data=input_data
                            )

        return (isolator.isolate_retcode, isolator.info)


    async def run_compilation(self, result):
        if self.df.compiler is not None:
            cretcode, info, binary = await self.compile()
            result['compile'] = info

            if cretcode != 0:
                return

            if binary is None:
                if result['compile']['stderr'].strip():
                    result['compile']['stderr'] += b'\n\n'

                result['compile']['stderr'] += b'Cannot find result binary.\n'
                return
        else:
            binary = camisole.utils.force_bytes(self.opts.get('source', ''))

        return binary


    async def run_tests(self, binary, result):
        tests = self.opts.get('tests', [{}])

        if tests:
            result['tests'] = [{}] * len(tests)

        for i, test in enumerate(tests):
            # user_execution overrides flat test-level isolate opts for user code
            test_opts = {**test, **test.get('user_execution', {})}
            retcode, info = await self.execute(binary, test_opts)

            assert info is not None
            
            result['tests'][i] = {
                'name': test.get('name', 'test{:03d}'.format(i)),
                **info
            }

            if retcode != 0 and (
                    test.get('fatal', False) or
                    self.opts.get('all_fatal', False)
                ):
                break


    async def run(self):
        result = {}
        binary = await self.run_compilation(result)

        if not binary:
            return result

        await self.run_tests(binary, result)
    
        return result

    def get_allowed_dirs(self):
        allowed_dirs = []
        allowed_dirs += self.df.allowed_dirs
        allowed_dirs += conf['allowed-dirs']
    
        return list(camisole.utils.uniquify(allowed_dirs))


    def compile_opt_out(self, output):
        return ['-o', output]


    def read_compiled(self, path, isolator) -> list[BinaryNamedFile] | None:
        try:
            with Path(path).open('rb') as c:
                return [("", c.read())]
        except (FileNotFoundError, PermissionError):
            pass


    def write_binary(self, path, binary):
        compiled = path / self.execute_filename()
        
        with compiled.open('wb') as c:
            c.write(binary)

        compiled.chmod(0o700)
        return compiled


    def source_filename(self):
        return 'source' + self.df.source_ext if self.df.source_ext else 'source'


    def execute_filename(self):
        if self.df.compiler is None and self.df.source_ext:
            return 'compiled' + self.df.source_ext

        return 'compiled'


    @staticmethod
    def filter_box_prefix(s):
        return re.sub('/var/(local/)?lib/isolate/[0-9]+', '', s)


    def compile_command(self, source, output):
        if self.df.compiler is None:
            return None

        return [
                self.df.compiler.cmd,
                *self.df.compiler.opts,
                *self.compile_opt_out(self.filter_box_prefix(output)),
                self.filter_box_prefix(source)
            ]


    def execute_command(self, output):
        cmd = []
    
        if self.df.interpreter is not None:
            cmd += [self.df.interpreter.cmd] + self.df.interpreter.opts

        return cmd + [self.filter_box_prefix(output)]


class PipelineLang(LangExecution):
    """
    A meta-language that compiles multiple sub-languages, passing the
    compilation result to the next sub-language, and eventually executing the
    last result.

    Subclass and define the ``sub_langs`` attribute.
    """
    sub_langs: List[Type[LangDefinition]] = list()


    @classmethod
    def register_language(cls, language_cls: type[LangDefinition]) -> None:
        super().register_language(language_cls)
        
        if hasattr(language_cls, 'sub_langs'):
            cls.sub_langs += [language_cls]


    @classmethod
    def required_binaries(cls):
        for lang_cls in cls.sub_langs:
            yield from lang_cls.required_binaries()


    async def run_compilation(self, result):
        source = camisole.utils.force_bytes(self.opts.get('source', ''))
        binary = None

        for lang_cls in self.sub_langs:
            assert lang_cls.executer is not None

            lang = lang_cls.executer({**self.opts, 'source': source})

            cretcode, info, binary = await lang.compile()
            result['compile'] = info

            if cretcode != 0:
                return

            if binary is None:
                if result['compile']['stderr'].strip():
                    result['compile']['stderr'] += b'\n\n'

                result['compile']['stderr'] += b'Cannot find result binary.\n'
                return

            # compile output is next stage input
            source = binary

        return binary


    async def compile(self):
        raise NotImplementedError()


class InteractiveLang(LangExecution):
    """
    Interactive execution mode with judge process.
    
    Runs user code and judge code in separate sandboxes with I/O mediation.
    Implements asymmetric filtering:
    - Judge → User: transparent passthrough
    - User → Judge: filtered through firewall rules
    """

    async def run(self):
        """
        Main execution pipeline for interactive mode.
        
        Compilation flow:
        1. Compile user code
        2. Compile judge code
        3. Run tests with I/O proxy
        """
        result = {}

        # Compile user code
        user_binary = await self.run_compilation(result)
        if not user_binary:
            return result

        # Compile judge code
        judge_binary = await self.run_judge_compilation(result)
        if not judge_binary:
            return result

        # Run interactive tests
        await self.run_interactive_tests(user_binary, judge_binary, result)

        return result

    async def run_judge_compilation(self, result):
        """
        Compile judge code in a separate sandbox.
        
        Returns:
            judge_binary: compiled judge code (bytes), or None if compilation failed
        """
        judge_source = self.opts.get('judge_source')
        judge_lang = self.opts.get('judge_lang')

        if not judge_source or not judge_lang:
            result['compile'] = result.get('compile', {})
            result['compile']['judge_error'] = 'judge_source and judge_lang required'
            return None

        # Look up judge language
        judge_lang_lower = judge_lang.lower()
        if judge_lang_lower not in LangExecution._registry:
            result['compile'] = result.get('compile', {})
            result['compile']['judge_error'] = f'judge language "{judge_lang}" not found'
            return None

        # Create execution context for judge language
        judge_exec_cls = LangExecution._registry[judge_lang_lower]
        judge_opts = {
            'lang': judge_lang,
            'source': judge_source,
            **self.opts.get('judge_compile', {}),
        }
        judge_exec = judge_exec_cls(judge_opts)

        # Store judge compilation info in result
        if 'compile' not in result:
            result['compile'] = {}

        # Interpreted language: no compile stage, use source directly.
        if judge_exec.df.compiler is None:
            result['compile']['judge'] = {
                'status': 'OK',
                'message': 'judge language has no compiler; using source directly',
            }
            return camisole.utils.force_bytes(judge_source)

        # Compiled language: compile judge code.
        judge_cretcode, judge_info, judge_binary = await judge_exec.compile()
        result['compile']['judge'] = judge_info

        if judge_cretcode != 0:
            return None

        if judge_binary is None:
            result['compile']['judge_error'] = 'Cannot find judge binary'
            return None

        return judge_binary

    async def run_interactive_tests(self, user_binary, judge_binary, result):
        """
        Run tests with interactive proxy I/O mediation.
        
        Each test runs user and judge in separate sandboxes with I/O proxy.
        """
        import camisole.proxy

        tests = self.opts.get('tests', [{}])
        if tests:
            result['tests'] = [{}] * len(tests)

        for i, test in enumerate(tests):
            # Prepare firewall rules if specified
            firewall_rules = None
            if test.get('firewall_rules'):
                firewall_rules = camisole.proxy.FirewallRules(
                    allowed_chars=test['firewall_rules'].get('allowed_chars'),
                    max_line_length=test['firewall_rules'].get('max_line_length'),
                    max_total_bytes=test['firewall_rules'].get('max_total_bytes'),
                    format_rules=test['firewall_rules'].get('format_rules', []),
                    violation_action=test['firewall_rules'].get('violation_action', 'STOP'),
                )

            # Extract isolate options for user and judge.
            # Flat test-level isolate opts provide backward-compatible defaults
            # for both user and judge; user_execution / judge_execution override
            # them selectively.
            user_opts = {**self.opts.get('execute', {}), **test,
                         **test.get('user_execution', {})}

            isolate_option_keys = {
                'extra-time', 'fsize', 'mem', 'processes', 'quota', 'stack', 'time', 'virt-mem', 'wall-time'
            }
            judge_opts = {k: v for k, v in test.items() if k in isolate_option_keys}
            judge_opts = {**judge_opts, **test.get('judge_execution', {})}

            # Run interactive test via proxy
            proxy_result = await self._run_interactive_test_via_proxy(
                user_binary, user_opts,
                judge_binary, judge_opts,
                firewall_rules=firewall_rules,
                judge_fault_exitcode=test.get(
                    'judge_fault_exitcode',
                    self.opts.get('judge_fault_exitcode')
                ),
            )

            # Format result
            test_result = {
                'name': test.get('name', 'test{:03d}'.format(i)),
                **proxy_result.to_dict(),
            }
            result['tests'][i] = test_result

            # Check if fatal
            if proxy_result.verdict != camisole.proxy.ProxyErrorClass.PASS and (
                    test.get('fatal', False) or
                    self.opts.get('all_fatal', False)
                ):
                break

    async def _run_interactive_test_via_proxy(self, user_binary, user_opts,
                                             judge_binary, judge_opts,
                                             firewall_rules=None,
                                             judge_fault_exitcode=None):
        """
        Run a single interactive test via proxy.
        
        Creates two isolators (user and judge) and mediates their I/O.
        """
        import camisole.proxy

        # Create user isolator
        user_isolator = camisole.isolate.Isolator(user_opts, 
            allowed_dirs=self.get_allowed_dirs())
        
        # Create judge isolator
        judge_isolator = camisole.isolate.Isolator(judge_opts,
            allowed_dirs=self.get_allowed_dirs())

        try:
            proxy_result = None

            async with user_isolator, judge_isolator:
                # Set up user sandbox
                assert user_isolator.path is not None
                wd_user = Path(user_isolator.path)
                env_user = {'HOME': self.filter_box_prefix(str(wd_user))}
                compiled_user = self.write_binary(wd_user, user_binary)
                env_user = {**env_user, **(self.df.interpreter.env if self.df.interpreter else {})}

                # Set up judge sandbox
                assert judge_isolator.path is not None
                wd_judge = Path(judge_isolator.path)
                env_judge = {'HOME': self.filter_box_prefix(str(wd_judge))}
                
                # Determine judge language for execution
                judge_lang = self.opts.get('judge_lang', '').lower()
                judge_df = LangExecution._definition_registry.get(judge_lang)
                
                if not judge_df:
                    return camisole.proxy.ProxyResult(
                        verdict=camisole.proxy.ProxyErrorClass.JUDGE_RUNTIME_ERROR,
                        error_message=f"Judge language {judge_lang} not found"
                    )
                
                compiled_judge = self._write_judge_binary(wd_judge, judge_binary, judge_df)
                env_judge = {**env_judge, **(judge_df.interpreter.env if judge_df.interpreter else {})}

                # Build commands
                user_inner_cmd = self.execute_command(str(compiled_user))
                judge_inner_cmd = self._judge_execute_command(str(compiled_judge), judge_df)

                # IMPORTANT: interactive processes must still run inside isolate.
                # We wrap both commands with isolate --run so /box paths are valid.
                user_cmd = self._build_interactive_isolate_cmd(
                    user_isolator,
                    user_inner_cmd,
                    env=env_user,
                )
                judge_cmd = self._build_interactive_isolate_cmd(
                    judge_isolator,
                    judge_inner_cmd,
                    env=env_judge,
                )

                # Create proxy with firewall rules
                proxy = camisole.proxy.InteractiveProxy(
                    firewall_rules=firewall_rules,
                    record_transcript=False,  # can make configurable
                    timeout=30.0,  # can make configurable via opts
                    judge_fault_exitcode=judge_fault_exitcode,
                )

                # Run proxy
                proxy_result = await proxy.run(user_cmd, judge_cmd)

                # Populate isolator stdout/stderr so that Isolator.__aexit__
                # produces a well-formed info dict.  Because the interactive
                # proxy streams I/O directly through pipes (bypassing
                # isolator.run()), the Isolator never sets these attributes;
                # they remain None and would cause NoneType errors anywhere
                # info['stdout'] or info['stderr'] is consumed downstream.
                user_isolator.stdout = b''
                user_isolator.stderr = b''
                judge_isolator.stdout = bytes(proxy.judge_output_buffer)
                judge_isolator.stderr = b''

            # Isolator metadata is parsed on __aexit__. Use it to retrieve the
            # real sandboxed program exit codes (not isolate wrapper exit code).
            if proxy_result is not None:
                user_meta = user_isolator.meta or {}
                judge_meta = judge_isolator.meta or {}

                user_status = user_meta.get('status')
                judge_status = judge_meta.get('status')

                # If isolate reports hard failures, trust these statuses first.
                if proxy_result.firewall_violation is None:
                    if user_status == 'TIMED_OUT':
                        proxy_result.verdict = camisole.proxy.ProxyErrorClass.USER_TIMEOUT
                    elif judge_status == 'TIMED_OUT':
                        proxy_result.verdict = camisole.proxy.ProxyErrorClass.JUDGE_TIMEOUT
                    elif user_status == 'OUT_OF_MEMORY':
                        proxy_result.verdict = camisole.proxy.ProxyErrorClass.RESOURCE_LIMIT_EXCEEDED
                        proxy_result.resource_limit_exceeded = 'user_memory'
                    elif judge_status == 'OUT_OF_MEMORY':
                        proxy_result.verdict = camisole.proxy.ProxyErrorClass.RESOURCE_LIMIT_EXCEEDED
                        proxy_result.resource_limit_exceeded = 'judge_memory'

                user_prog_exit = user_meta.get('exitcode')
                judge_prog_exit = judge_meta.get('exitcode')

                # Trust program exit codes when isolate status is OK or
                # RUNTIME_ERROR.  RUNTIME_ERROR means the program exited with a
                # non-zero code, and isolate records that exit code accurately in
                # its meta file.  For other statuses (TIMED_OUT, SIGNALED,
                # OUT_OF_MEMORY, INTERNAL_ERROR) isolate may write the default
                # exitcode=0 placeholder, so those are not used.
                if user_status in ('OK', 'RUNTIME_ERROR') and isinstance(user_prog_exit, int):
                    proxy_result.user_exit_code = user_prog_exit
                if judge_status in ('OK', 'RUNTIME_ERROR') and isinstance(judge_prog_exit, int):
                    proxy_result.judge_exit_code = judge_prog_exit

                user_exitsig = user_meta.get('exitsig')
                judge_exitsig = judge_meta.get('exitsig')
                if isinstance(user_exitsig, int) and user_exitsig > 0:
                    proxy_result.user_crashed = True
                    proxy_result.user_signal = user_exitsig
                if isinstance(judge_exitsig, int) and judge_exitsig > 0:
                    proxy_result.judge_crashed = True
                    proxy_result.judge_signal = judge_exitsig

                # Honor custom judge fault code using real program exit code.
                if (
                    judge_fault_exitcode is not None
                    and isinstance(proxy_result.judge_exit_code, int)
                    and proxy_result.judge_exit_code == judge_fault_exitcode
                    and proxy_result.firewall_violation is None
                ):
                    proxy_result.verdict = camisole.proxy.ProxyErrorClass.FAULT
                elif (
                    proxy_result.verdict == camisole.proxy.ProxyErrorClass.JUDGE_RUNTIME_ERROR
                    and isinstance(proxy_result.judge_exit_code, int)
                    and proxy_result.judge_exit_code == 0
                    and judge_status == 'OK'
                ):
                    # If isolate wrapper failed but program exit code is 0,
                    # normalize verdict to PASS.
                    proxy_result.verdict = camisole.proxy.ProxyErrorClass.PASS

                return proxy_result

            return camisole.proxy.ProxyResult(
                verdict=camisole.proxy.ProxyErrorClass.PROXY_COMMUNICATION_ERROR,
                error_message='interactive proxy returned no result'
            )

        except Exception as e:
            logging.error(f"Error in interactive test: {e}")
            return camisole.proxy.ProxyResult(
                verdict=camisole.proxy.ProxyErrorClass.PROXY_COMMUNICATION_ERROR,
                error_message=str(e)
            )

    def _write_judge_binary(self, path: Path, binary: bytes, judge_df: Type[LangDefinition]) -> Path:
        """
        Write judge binary to sandbox, similar to write_binary but for judge language.
        """
        # Determine filename based on judge language
        if judge_df.source_ext:
            filename = 'judge' + judge_df.source_ext
        else:
            filename = 'judge'

        compiled = path / filename
        with compiled.open('wb') as f:
            f.write(binary)
        compiled.chmod(0o700)
        return compiled

    def _judge_execute_command(self, judge_path: str, judge_df: Type[LangDefinition]) -> List[str]:
        """Build command to execute judge, using judge's language definition."""
        cmd = []
        
        if judge_df.interpreter is not None:
            cmd += [judge_df.interpreter.cmd] + judge_df.interpreter.opts
        
        return cmd + [self.filter_box_prefix(judge_path)]

    def _build_interactive_isolate_cmd(self, isolator, inner_cmd: List[str], env=None) -> List[str]:
        """
        Build an isolate --run command suitable for streaming interactive I/O.

        Unlike Isolator.run(), we do not force --stdout/--stderr file redirection,
        so the proxy can stream pipes directly between user and judge.
        """
        cmd_run = isolator.cmd_base[:]
        cmd_run += list(
            itertools.chain(
                *[('-d', d) for d in isolator.allowed_dirs]
            )
        )

        for opt in camisole.isolate.CAMISOLE_OPTIONS:
            v = isolator.opts.get(opt)
            iopt = camisole.isolate.CAMISOLE_TO_ISOLATE_OPTS.get(opt, opt)

            if v is not None:
                cmd_run.append(f'--{iopt}={v!s}')
            elif iopt == 'processes':
                cmd_run.append('-p')

        for e in ['PATH', 'LD_LIBRARY_PATH', 'LANG']:
            env_value = os.getenv(e)
            if env_value:
                cmd_run += ['--env', e + '=' + env_value]

        for key, value in (env or {}).items():
            cmd_run += [f'--env={key}={value}']

        cmd_run += ['--meta={}'.format(isolator.meta_file.name)]
        cmd_run += ['--run', '--']
        cmd_run += inner_cmd

        return cmd_run
