from camisole.models import LangDefinition, Program

reference=r'''
#include <stdio.h>

int main(void)
{
    printf("42\n");
    return 0;
}
'''

class C(LangDefinition):
    source_ext = '.c'
    compiler = Program('gcc',  opts=['-std=c11', '-Wall', '-Wextra', '-O2', '-lm'])
    reference_source = reference

