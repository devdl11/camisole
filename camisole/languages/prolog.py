from camisole.models import LangDefinition, Program

reference = r'''
:- write('42\n').
'''

class Prolog(LangDefinition):
    source_ext = '.pl'
    interpreter = Program('swipl', opts=['--quiet', '-t', 'halt'], version_opt='--version')
    reference_source = reference
