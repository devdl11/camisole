from camisole.models import LangDefinition, Program

reference = r'''
print("42")
'''

class Python(LangDefinition):
    source_ext = '.py'
    interpreter = Program('python3', opts=['-S'])
    reference_source = reference
