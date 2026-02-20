from camisole.models import LangDefinition, Program

reference=r"""
with Ada.Text_IO; use Ada.Text_IO;
procedure Hello is
begin
    Put_Line("42");
end Hello;
"""

class Ada(LangDefinition):
    source_ext = '.adb'
    compiler = Program('gnatmake', opts=['-f'])
    reference_source = reference
