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
import logging
import os
import re
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Sequence, Type

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
    name: Optional[str]

    source_ext: Optional[str]
    compiler: Optional[Program]
    interpreter: Optional[Program]
    allowed_dirs: List[str]
    extra_binaries: Dict[str, Program]
    reference_source: Optional[str]
    executer: Optional[Type['LangExecution']]


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
            retcode, info = await self.execute(binary, test)

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
