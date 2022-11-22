# Generated from GitlabRule.g4 by ANTLR 4.11.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .GitlabRuleParser import GitlabRuleParser
else:
    from GitlabRuleParser import GitlabRuleParser

# This class defines a complete generic visitor for a parse tree produced by GitlabRuleParser.

class GitlabRuleVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by GitlabRuleParser#parens.
    def visitParens(self, ctx:GitlabRuleParser.ParensContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GitlabRuleParser#regex.
    def visitRegex(self, ctx:GitlabRuleParser.RegexContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GitlabRuleParser#compare.
    def visitCompare(self, ctx:GitlabRuleParser.CompareContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GitlabRuleParser#boolOr.
    def visitBoolOr(self, ctx:GitlabRuleParser.BoolOrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GitlabRuleParser#boolAnd.
    def visitBoolAnd(self, ctx:GitlabRuleParser.BoolAndContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GitlabRuleParser#variable.
    def visitVariable(self, ctx:GitlabRuleParser.VariableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GitlabRuleParser#match.
    def visitMatch(self, ctx:GitlabRuleParser.MatchContext):
        return self.visitChildren(ctx)



del GitlabRuleParser