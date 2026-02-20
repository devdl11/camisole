from camisole.models import LangDefinition, Program

reference = r'''
print("42")
'''

class Lua(LangDefinition):
    source_ext = '.lua'
    interpreter = Program('lua', version_opt='-v')
    reference_source = reference
