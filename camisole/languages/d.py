from camisole.models import LangDefinition, LangExecution, Program

reference=r'''
void main()
{
    import std.stdio: writeln;
    writeln("42");
}
'''

class DExecution(LangExecution):
    def compile_opt_out(self, output):
        # '-of' and its value as two distinct arguments is illegal (go figure)
        return ['-of' + output]


class D(LangDefinition):
    source_ext = '.d'
    compiler = Program('dmd')
    allowed_dirs = ['/etc']
    reference_source = reference
    executer = DExecution
