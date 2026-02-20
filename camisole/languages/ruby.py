from camisole.models import LangDefinition, Program

reference = r'''
puts "42"
'''

class Ruby(LangDefinition):
    source_ext = '.rb'
    interpreter = Program('ruby')
    reference_source = reference
