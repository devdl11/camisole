from camisole.models import LangDefinition, LangExecution, Program

reference=r'''
using System;
class Program
{
    public static void Main()
    {
        Console.WriteLine(42);
    }
}
'''

class CSharpExecution(LangExecution):
    def compile_opt_out(self, output):
        return ['-out:' + output]


class CSharp(LangDefinition, name="C#"):
    source_ext = '.cs'
    compiler = Program('mcs', opts=['-optimize+'])
    interpreter = Program('mono')
    allowed_dirs = ['/etc/mono']
    executer = CSharpExecution
    reference_source = reference

