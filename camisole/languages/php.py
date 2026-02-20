from camisole.models import LangDefinition, Program

reference = r'''
<?php
echo "42\n";
?>
'''

class PHP(LangDefinition):
    source_ext = '.php'
    interpreter = Program('php')
    reference_source = reference
