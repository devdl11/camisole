from camisole.models import LangDefinition, Program

reference = r'''
fn main() {
    println!("42");
}
'''

class Rust(LangDefinition):
    source_ext = '.rs'
    compiler = Program('rustc', opts=['-W', 'warnings', '-C', 'opt-level=3'])
    reference_source = reference
