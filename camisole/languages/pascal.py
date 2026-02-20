from camisole.models import LangDefinition, LangExecution, Program

reference = r'''
program main;
begin
    Writeln(42);
end.
'''

class PascalExecution(LangExecution):
    def compile_opt_out(self, output):
        return ['-o' + output]

class Pascal(LangDefinition):
    source_ext = '.pas'
    compiler = Program('fpc', opts=['-XD', '-Fainitc'], version_opt='-h', version_lines=1)
    reference_source = reference
    executer = PascalExecution
