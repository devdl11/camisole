from camisole.models import LangDefinition, Program

reference=r'''
#include <iostream>
int main()
{
    std::cout << 42 << std::endl;
    return 0;
}
'''

class CXX(LangDefinition, name="C++"):
    source_ext = '.cc'
    compiler = Program('g++', opts=['-std=c++17', '-Wall', '-Wextra', '-O2'])
    reference_source = reference

