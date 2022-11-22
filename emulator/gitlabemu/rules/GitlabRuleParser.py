# Generated from GitlabRule.g4 by ANTLR 4.11.1
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,12,34,2,0,7,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,
        0,1,0,1,0,1,0,1,0,1,0,1,0,3,0,21,8,0,1,0,1,0,1,0,1,0,1,0,1,0,5,0,
        29,8,0,10,0,12,0,32,9,0,1,0,0,1,0,1,0,0,2,1,0,3,4,1,0,5,6,39,0,20,
        1,0,0,0,2,3,6,0,-1,0,3,4,5,11,0,0,4,5,7,0,0,0,5,21,5,9,0,0,6,7,5,
        9,0,0,7,8,7,0,0,0,8,21,5,11,0,0,9,10,5,11,0,0,10,11,7,1,0,0,11,21,
        5,10,0,0,12,13,5,11,0,0,13,14,7,1,0,0,14,21,5,11,0,0,15,21,5,11,
        0,0,16,17,5,7,0,0,17,18,3,0,0,0,18,19,5,8,0,0,19,21,1,0,0,0,20,2,
        1,0,0,0,20,6,1,0,0,0,20,9,1,0,0,0,20,12,1,0,0,0,20,15,1,0,0,0,20,
        16,1,0,0,0,21,30,1,0,0,0,22,23,10,3,0,0,23,24,5,2,0,0,24,29,3,0,
        0,4,25,26,10,2,0,0,26,27,5,1,0,0,27,29,3,0,0,3,28,22,1,0,0,0,28,
        25,1,0,0,0,29,32,1,0,0,0,30,28,1,0,0,0,30,31,1,0,0,0,31,1,1,0,0,
        0,32,30,1,0,0,0,3,20,28,30
    ]

class GitlabRuleParser ( Parser ):

    grammarFileName = "GitlabRule.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'||'", "'&&'", "'=='", "'!='", "'=~'", 
                     "'!~'", "'('", "')'" ]

    symbolicNames = [ "<INVALID>", "OR", "AND", "EQ", "NE", "MATCH", "NMATCH", 
                      "OPAR", "CPAR", "STRING", "REGEX", "VARIABLE", "WHITESPACE" ]

    RULE_expr = 0

    ruleNames =  [ "expr" ]

    EOF = Token.EOF
    OR=1
    AND=2
    EQ=3
    NE=4
    MATCH=5
    NMATCH=6
    OPAR=7
    CPAR=8
    STRING=9
    REGEX=10
    VARIABLE=11
    WHITESPACE=12

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.11.1")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.op = None # Token

        def VARIABLE(self, i:int=None):
            if i is None:
                return self.getTokens(GitlabRuleParser.VARIABLE)
            else:
                return self.getToken(GitlabRuleParser.VARIABLE, i)

        def STRING(self):
            return self.getToken(GitlabRuleParser.STRING, 0)

        def EQ(self):
            return self.getToken(GitlabRuleParser.EQ, 0)

        def NE(self):
            return self.getToken(GitlabRuleParser.NE, 0)

        def REGEX(self):
            return self.getToken(GitlabRuleParser.REGEX, 0)

        def MATCH(self):
            return self.getToken(GitlabRuleParser.MATCH, 0)

        def NMATCH(self):
            return self.getToken(GitlabRuleParser.NMATCH, 0)

        def OPAR(self):
            return self.getToken(GitlabRuleParser.OPAR, 0)

        def expr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(GitlabRuleParser.ExprContext)
            else:
                return self.getTypedRuleContext(GitlabRuleParser.ExprContext,i)


        def CPAR(self):
            return self.getToken(GitlabRuleParser.CPAR, 0)

        def AND(self):
            return self.getToken(GitlabRuleParser.AND, 0)

        def OR(self):
            return self.getToken(GitlabRuleParser.OR, 0)

        def getRuleIndex(self):
            return GitlabRuleParser.RULE_expr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExpr" ):
                return visitor.visitExpr(self)
            else:
                return visitor.visitChildren(self)



    def expr(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = GitlabRuleParser.ExprContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 0
        self.enterRecursionRule(localctx, 0, self.RULE_expr, _p)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 20
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,0,self._ctx)
            if la_ == 1:
                self.state = 3
                self.match(GitlabRuleParser.VARIABLE)
                self.state = 4
                localctx.op = self._input.LT(1)
                _la = self._input.LA(1)
                if not(_la==3 or _la==4):
                    localctx.op = self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 5
                self.match(GitlabRuleParser.STRING)
                pass

            elif la_ == 2:
                self.state = 6
                self.match(GitlabRuleParser.STRING)
                self.state = 7
                localctx.op = self._input.LT(1)
                _la = self._input.LA(1)
                if not(_la==3 or _la==4):
                    localctx.op = self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 8
                self.match(GitlabRuleParser.VARIABLE)
                pass

            elif la_ == 3:
                self.state = 9
                self.match(GitlabRuleParser.VARIABLE)
                self.state = 10
                localctx.op = self._input.LT(1)
                _la = self._input.LA(1)
                if not(_la==5 or _la==6):
                    localctx.op = self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 11
                self.match(GitlabRuleParser.REGEX)
                pass

            elif la_ == 4:
                self.state = 12
                self.match(GitlabRuleParser.VARIABLE)
                self.state = 13
                localctx.op = self._input.LT(1)
                _la = self._input.LA(1)
                if not(_la==5 or _la==6):
                    localctx.op = self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 14
                self.match(GitlabRuleParser.VARIABLE)
                pass

            elif la_ == 5:
                self.state = 15
                self.match(GitlabRuleParser.VARIABLE)
                pass

            elif la_ == 6:
                self.state = 16
                self.match(GitlabRuleParser.OPAR)
                self.state = 17
                self.expr(0)
                self.state = 18
                self.match(GitlabRuleParser.CPAR)
                pass


            self._ctx.stop = self._input.LT(-1)
            self.state = 30
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,2,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 28
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,1,self._ctx)
                    if la_ == 1:
                        localctx = GitlabRuleParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 22
                        if not self.precpred(self._ctx, 3):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 3)")
                        self.state = 23
                        localctx.op = self.match(GitlabRuleParser.AND)
                        self.state = 24
                        self.expr(4)
                        pass

                    elif la_ == 2:
                        localctx = GitlabRuleParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 25
                        if not self.precpred(self._ctx, 2):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                        self.state = 26
                        localctx.op = self.match(GitlabRuleParser.OR)
                        self.state = 27
                        self.expr(3)
                        pass

             
                self.state = 32
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,2,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx



    def sempred(self, localctx:RuleContext, ruleIndex:int, predIndex:int):
        if self._predicates == None:
            self._predicates = dict()
        self._predicates[0] = self.expr_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def expr_sempred(self, localctx:ExprContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 3)
         

            if predIndex == 1:
                return self.precpred(self._ctx, 2)
         




