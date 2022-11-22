from typing import Dict, Optional

from antlr4 import InputStream, CommonTokenStream
from antlr4.Token import CommonToken

from .GitlabRuleParser import GitlabRuleParser
from .GitlabRuleLexer import GitlabRuleLexer
from .GitlabRuleVisitor import GitlabRuleVisitor


class RuleVisitor(GitlabRuleVisitor):
    def __init__(self, variables: Optional[Dict[str, str]] = None):
        self.variables: Dict[str, str] = {}
        if variables:
            self.variables.update(variables)

    def get_variable_name(self, symbol: CommonToken):
        if symbol.type == GitlabRuleLexer.VARIABLE:
            name = symbol.text[1:]
            return name
        return ""

    def resolve_variable(self, symbol: CommonToken):
        text = symbol.text
        name = self.get_variable_name(symbol)
        if name:
            return self.variables.get(name, "")
        # strip quotes
        return text[1:-1]

    def visitVariable(self, ctx: GitlabRuleParser.VariableContext):
        """Return True if VARNAME is set to anything except the empty string"""
        assert len(ctx.children) == 1
        name = self.get_variable_name(ctx.children[0].symbol)
        return self.variables.get(name, "") != ""

    def visitCompare(self, ctx: GitlabRuleParser.CompareContext):
        """Compare strings/variables for equality"""
        assert len(ctx.children) == 3
        assert ctx.op.type in [GitlabRuleLexer.EQ, GitlabRuleLexer.NE]
        left = self.resolve_variable(ctx.children[0].symbol)
        right = self.resolve_variable(ctx.children[2].symbol)

        if ctx.op.type == GitlabRuleLexer.EQ:
            return left == right
        return left != right

    def visitBoolAnd(self, ctx: GitlabRuleParser.BoolAndContext):
        left = self.visit(ctx.expr(0))
        right = self.visit(ctx.expr(1))
        return left and right

    def visitBoolOr(self, ctx:GitlabRuleParser.BoolOrContext):
        left = self.visit(ctx.expr(0))
        right = self.visit(ctx.expr(1))
        return left or right


def evaluate_rule(rule: str, variables: Dict[str, str]):
    lexer = GitlabRuleLexer(InputStream(rule))
    stream = CommonTokenStream(lexer)
    parser = GitlabRuleParser(stream)
    tree = parser.expr()
    visitor = RuleVisitor(variables)
    return visitor.visit(tree)
