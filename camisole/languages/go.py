from camisole.models import LangDefinition, Program

reference = r'''
package main
import "fmt"
func main() {
    fmt.Println("42")
}
'''

class Go(LangDefinition):
    source_ext = '.go'
    compiler = Program('go', opts=['build', '-buildmode=exe'],
                       version_opt='version',
                       env={'GOCACHE':'/box/.gocache'})
    reference_source = reference

