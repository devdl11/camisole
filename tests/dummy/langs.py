from camisole.models import LangExecution, Program


class CompiledLang(LangExecution):
    compiler = Program('echo')


class InterpretedLang(LangExecution):
    interpreter = Program('echo')
