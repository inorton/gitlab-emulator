from typing import Dict, Optional

from antlr4 import InputStream, CommonTokenStream
from .GitlabRuleParser import GitlabRuleParser
from .GitlabRuleLexer import GitlabRuleLexer
from .GitlabRuleVisitor import GitlabRuleVisitor


class RuleVisitor(GitlabRuleVisitor):
    def __init__(self, variables: Optional[Dict[str, str]] = None):
        self.variables: Dict[str, str] = {}
        if variables:
            self.variables.update(variables)

    def visitExpr(self, ctx: GitlabRuleParser.ExprContext):
        value = super().visitExpr(ctx)

        return value


def evaluate_rule(rule: str, variables: Dict[str, str]):
    lexer = GitlabRuleLexer(InputStream(rule))
    stream = CommonTokenStream(lexer)
    parser = GitlabRuleParser(stream)
    tree = parser.expr()
    visitor = RuleVisitor(variables)
    return visitor.visit(tree)
