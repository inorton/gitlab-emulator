# Generated from GitlabRule.g4 by ANTLR 4.11.1
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
    from typing import TextIO
else:
    from typing.io import TextIO


def serializedATN():
    return [
        4,0,12,78,6,-1,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,
        6,7,6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,1,0,1,0,1,0,1,
        1,1,1,1,1,1,2,1,2,1,2,1,3,1,3,1,3,1,4,1,4,1,4,1,5,1,5,1,5,1,6,1,
        6,1,7,1,7,1,8,1,8,5,8,50,8,8,10,8,12,8,53,9,8,1,8,1,8,1,9,1,9,5,
        9,59,8,9,10,9,12,9,62,9,9,1,9,1,9,1,10,1,10,4,10,68,8,10,11,10,12,
        10,69,1,11,4,11,73,8,11,11,11,12,11,74,1,11,1,11,0,0,12,1,1,3,2,
        5,3,7,4,9,5,11,6,13,7,15,8,17,9,19,10,21,11,23,12,1,0,4,1,0,34,34,
        1,0,47,47,4,0,48,57,65,90,95,95,97,122,3,0,9,10,13,13,32,32,81,0,
        1,1,0,0,0,0,3,1,0,0,0,0,5,1,0,0,0,0,7,1,0,0,0,0,9,1,0,0,0,0,11,1,
        0,0,0,0,13,1,0,0,0,0,15,1,0,0,0,0,17,1,0,0,0,0,19,1,0,0,0,0,21,1,
        0,0,0,0,23,1,0,0,0,1,25,1,0,0,0,3,28,1,0,0,0,5,31,1,0,0,0,7,34,1,
        0,0,0,9,37,1,0,0,0,11,40,1,0,0,0,13,43,1,0,0,0,15,45,1,0,0,0,17,
        47,1,0,0,0,19,56,1,0,0,0,21,65,1,0,0,0,23,72,1,0,0,0,25,26,5,124,
        0,0,26,27,5,124,0,0,27,2,1,0,0,0,28,29,5,38,0,0,29,30,5,38,0,0,30,
        4,1,0,0,0,31,32,5,61,0,0,32,33,5,61,0,0,33,6,1,0,0,0,34,35,5,33,
        0,0,35,36,5,61,0,0,36,8,1,0,0,0,37,38,5,61,0,0,38,39,5,126,0,0,39,
        10,1,0,0,0,40,41,5,33,0,0,41,42,5,126,0,0,42,12,1,0,0,0,43,44,5,
        40,0,0,44,14,1,0,0,0,45,46,5,41,0,0,46,16,1,0,0,0,47,51,5,34,0,0,
        48,50,8,0,0,0,49,48,1,0,0,0,50,53,1,0,0,0,51,49,1,0,0,0,51,52,1,
        0,0,0,52,54,1,0,0,0,53,51,1,0,0,0,54,55,5,34,0,0,55,18,1,0,0,0,56,
        60,5,47,0,0,57,59,8,1,0,0,58,57,1,0,0,0,59,62,1,0,0,0,60,58,1,0,
        0,0,60,61,1,0,0,0,61,63,1,0,0,0,62,60,1,0,0,0,63,64,5,47,0,0,64,
        20,1,0,0,0,65,67,5,36,0,0,66,68,7,2,0,0,67,66,1,0,0,0,68,69,1,0,
        0,0,69,67,1,0,0,0,69,70,1,0,0,0,70,22,1,0,0,0,71,73,7,3,0,0,72,71,
        1,0,0,0,73,74,1,0,0,0,74,72,1,0,0,0,74,75,1,0,0,0,75,76,1,0,0,0,
        76,77,6,11,0,0,77,24,1,0,0,0,5,0,51,60,69,74,1,6,0,0
    ]

class GitlabRuleLexer(Lexer):

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    OR = 1
    AND = 2
    EQ = 3
    NE = 4
    MATCH = 5
    NMATCH = 6
    OPAR = 7
    CPAR = 8
    STRING = 9
    REGEX = 10
    VARIABLE = 11
    WHITESPACE = 12

    channelNames = [ u"DEFAULT_TOKEN_CHANNEL", u"HIDDEN" ]

    modeNames = [ "DEFAULT_MODE" ]

    literalNames = [ "<INVALID>",
            "'||'", "'&&'", "'=='", "'!='", "'=~'", "'!~'", "'('", "')'" ]

    symbolicNames = [ "<INVALID>",
            "OR", "AND", "EQ", "NE", "MATCH", "NMATCH", "OPAR", "CPAR", 
            "STRING", "REGEX", "VARIABLE", "WHITESPACE" ]

    ruleNames = [ "OR", "AND", "EQ", "NE", "MATCH", "NMATCH", "OPAR", "CPAR", 
                  "STRING", "REGEX", "VARIABLE", "WHITESPACE" ]

    grammarFileName = "GitlabRule.g4"

    def __init__(self, input=None, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.11.1")
        self._interp = LexerATNSimulator(self, self.atn, self.decisionsToDFA, PredictionContextCache())
        self._actions = None
        self._predicates = None

