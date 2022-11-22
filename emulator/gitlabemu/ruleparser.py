import re
from typing import Dict, Optional

from antlr4 import InputStream, CommonTokenStream
from antlr4.Token import CommonToken

from gitlabemu.rules.GitlabRuleParser import GitlabRuleParser
from gitlabemu.rules.GitlabRuleLexer import GitlabRuleLexer
from gitlabemu.rules.GitlabRuleVisitor import GitlabRuleVisitor


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
        if text[0] == '"':
            return text[1:-1]
        return text

    def visitRegex(self, ctx: GitlabRuleParser.RegexContext):
        assert len(ctx.children) == 1
        return ctx.children[0].symbol.text

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

    def visitMatch(self, ctx: GitlabRuleParser.MatchContext):
        assert len(ctx.children) == 3
        assert ctx.op.type in [GitlabRuleLexer.MATCH, GitlabRuleLexer.NMATCH]
        left = self.resolve_variable(ctx.children[0].symbol)
        right = self.resolve_variable(ctx.children[2].symbol)
        if right.startswith("/") and right.endswith("/"):
            # is a regex
            patt = re.compile(right[1:-1])
            matched = patt.search(left)
            if ctx.op.type == GitlabRuleLexer.MATCH:
                return matched is not None
            return matched is None
        return False

    def visitBoolAnd(self, ctx: GitlabRuleParser.BoolAndContext):
        left = self.visit(ctx.expr(0))
        right = self.visit(ctx.expr(1))
        return left and right

    def visitBoolOr(self, ctx:GitlabRuleParser.BoolOrContext):
        left = self.visit(ctx.expr(0))
        right = self.visit(ctx.expr(1))
        return left or right

    def visitParens(self, ctx: GitlabRuleParser.ParensContext):
        return self.visit(ctx.expr())


def evaluate_rule(rule: str, variables: Dict[str, str]):
    lexer = GitlabRuleLexer(InputStream(rule))
    stream = CommonTokenStream(lexer)
    parser = GitlabRuleParser(stream)
    tree = parser.expr()
    visitor = RuleVisitor(variables)
    return visitor.visit(tree)
