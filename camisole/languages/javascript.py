from camisole.models import LangDefinition, Program

reference = r'''
process.stdout.write('42\n');
'''

class Javascript(LangDefinition):
    source_ext = '.js'
    interpreter = Program('node')
    reference_source = reference
