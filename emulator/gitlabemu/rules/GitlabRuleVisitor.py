# Generated from GitlabRule.g4 by ANTLR 4.11.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .GitlabRuleParser import GitlabRuleParser
else:
    from GitlabRuleParser import GitlabRuleParser

# This class defines a complete generic visitor for a parse tree produced by GitlabRuleParser.

class GitlabRuleVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by GitlabRuleParser#expr.
    def visitExpr(self, ctx:GitlabRuleParser.ExprContext):
        return self.visitChildren(ctx)



del GitlabRuleParser