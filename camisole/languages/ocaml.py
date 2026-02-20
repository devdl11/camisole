from camisole.models import LangDefinition, Program


class OCaml(LangDefinition):
    source_ext = '.ml'
    compiler = Program('ocamlopt', opts=['-w', 'A'], version_opt='-v')
    reference_source = r'print_int 42; print_string "\n";'
