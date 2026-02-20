from camisole.models import LangDefinition, Program

reference = r'''
module Main where main = putStrLn "42"
'''

class Haskell(LangDefinition):
    source_ext = '.hs'
    compiler = Program('ghc', opts=['-dynamic', '-O2'])
    reference_source = reference
