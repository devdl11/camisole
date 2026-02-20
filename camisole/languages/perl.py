from camisole.models import LangDefinition, Program

reference = r'''
print "42\n";
'''

class Perl(LangDefinition):
    source_ext = '.pl'
    interpreter = Program('perl')
    reference_source = reference
