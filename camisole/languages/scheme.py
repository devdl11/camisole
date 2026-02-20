from camisole.models import LangDefinition, Program

reference = r'''
(display "42")(newline)
'''

class Scheme(LangDefinition):
    source_ext = '.scm'
    interpreter = Program('gsi', version_opt='-v')
    reference_source = reference
