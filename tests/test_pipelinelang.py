import pytest

from camisole.languages.c import C
from camisole.models import PipelineLang, LangExecution, LangDefinition, Program

class CopyExecutor(LangExecution):
    def compile_command(self, source, output):
        assert self.df.compiler, "CopyExecutor should have a compiler defined"

        return [self.df.compiler.cmd,
                self.filter_box_prefix(source),
                self.filter_box_prefix(output)]


class Copy(LangDefinition, register=False):
    source_ext = '.a'
    compiler = Program('cp')
    executer = CopyExecutor


class BadeCopyExecutor(LangExecution):
    def compile_command(self, source, output):
        return super().compile_command(source, output + 'bad')


class BadCopy(Copy, register=False):
    executer = BadeCopyExecutor


class BadeCompilerExecutor(LangExecution):
    def compile_command(self, source, output):
        assert self.df.compiler, "BadeCompilerExecutor should have a compiler defined"

        return [self.df.compiler.cmd, *self.df.compiler.opts]


class BadCompiler(LangDefinition, register=False):
    source_ext = '.a'
    compiler = Program('sh', opts=['-c', 'echo BadCompiler is bad >&2'])
    executer = BadeCompilerExecutor


@pytest.mark.asyncio
async def test_pipeline_success():
    class Pipeline(PipelineLang):
        sub_langs = [Copy, Copy, C]

    p = Pipeline({'source': C.reference_source, 'tests': [{}]})
    result = await p.run()

    assert result['tests'][0]['stdout'] == b'42\n'


@pytest.mark.asyncio
async def test_pipeline_failure_return_nonzero():
    class Pipeline(PipelineLang):
        sub_langs = [C, C]

    p = Pipeline({'source': C.reference_source, 'tests': [{}]})

    result = await p.run()

    assert result['compile']['meta']['status'] == 'RUNTIME_ERROR'
    assert result['compile']['meta']['exitcode'] == 1


@pytest.mark.asyncio
async def test_pipeline_failure_does_not_create_binary_while_returning_zero():
    class Pipeline(PipelineLang):
        sub_langs = [BadCopy, C]

    p = Pipeline({'source': C.reference_source, 'tests': [{}]})

    result = await p.run()

    stderr = result['compile']['stderr'].decode().lower()
    assert 'cannot find result binary' in stderr



@pytest.mark.asyncio
async def test_pipeline_failure_compiler_returns_nonzero():
    class Pipeline(PipelineLang):
        sub_langs = [BadCompiler, C]

    p = Pipeline({'source': C.reference_source, 'tests': [{}]})

    result = await p.run()

    stderr = result['compile']['stderr'].decode().lower()
    assert 'badcompiler is bad' in stderr
    assert 'cannot find result binary' in stderr
