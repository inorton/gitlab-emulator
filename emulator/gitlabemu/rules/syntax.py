"""Parse rules

Partly guided and inspired by https://jayconrod.com/posts/38/a-simple-interpreter-from-scratch-in-python-part-2
"""
import re
#
# Gitlab rule expressions only really have comparison and boolean operators and basic grouping,
#
# an AST for a basic expresion of:
#           '$COLOR == "red"'
# would be:
#
#            compare(==)
#             /      \
#          $COLOR   "red"
#
# a more complex AST of a compound rule:
#          '("red" == $COLOR) && ($SIZE =~ /large/)'
# would be
#
#            logical(&&)
#            /         \
#     compare(==)     compare(=~)
#      /    \           /     \
#  "red"   $COLOR    $SIZE    /large/
#

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union
from .lexer import Parser, Token


EQUAL = "=="
MATCH = "=~"
NOTEQUAL = "!="
NOTMATCH = "!~"

COMPARISONS = [EQUAL, MATCH, NOTMATCH, NOTEQUAL]

OR = "||"
AND = "&&"

LOGICAL = [OR, AND]


class TreeNode:
    def __init__(self):
        self.parent: Optional["TreeNode"] = None
        self.op: Optional[str] = None
        self.left: Optional[Union[Token, "TreeNode"]] = None
        self.right: Optional[Union[Token, "TreeNode"]] = None

    def put(self, item: Union[Token, "TreeNode"]):
        if isinstance(item, TreeNode):
            item.parent = self
        if not self.left:
            self.left = item
        elif not self.right:
            self.right = item
        else:
            assert False, f"bad tree put {item}"

    @property
    def depth(self) -> int:
        count = 0
        current = self
        while current is not None:
            current = current.parent
            count += 1
        return count

    def __repr__(self):
        if self.op:
            if self.left and self.right:
                return str(f"({self.left} {self.op} {self.right})")
            else:
                return str(f"({self.op} {self.left})")
        return ""

class ParserBase(ABC):
    @abstractmethod
    def __call__(self, tokens: List[Token]) -> Optional[TreeNode]:
        pass

    def __repr__(self):
        return str(type(self))


class Compare(Parser):
    def __call__(self, tokens: List[Token]) -> Optional[TreeNode]:
        # expect 3 tokens, with middle as a comparison
        if len(tokens) >= 3:
            middle = tokens[1]
            if middle.value in COMPARISONS:
                result = TreeNode()
                result.left = tokens.pop(0)
                result.op = tokens.pop(0).value
                result.right = tokens.pop(0)
                return result
        return None

class Boolean(Parser):
    op = "XX"

    def __call__(self, tokens: List[Token]) -> Optional[TreeNode]:
        if len(tokens) > 0:
            if tokens[0].value == self.op:
                result = TreeNode()
                result.op = tokens.pop(0).value
                return result
        return None

class BooleanAnd(Boolean):
    op = "&&"


class BooleanOr(Boolean):
    op = "||"


class Brace(Parser):
    brace = "xx"

    def __call__(self, tokens: List[Token]) -> Optional[TreeNode]:
        if len(tokens) > 0:
            if tokens[0].value == self.brace:
                result = TreeNode()
                result.op = self.brace
                tokens.pop(0)
                return result
        return None

class OpenBrace(Brace):
    brace = "("


class CloseBrace(Brace):
    brace = ")"


class BareVariable(Parser):
    def __call__(self, tokens: List[Token]) -> Optional[TreeNode]:
        if len(tokens) > 0:
            if tokens[0].value.startswith("$"):
                result = TreeNode()
                result.op = "defined"
                result.left = tokens.pop(0)
                return result
        return None


class Rule:
    def __init__(self, text: str, tokens: List[Token]):
        self.text = text
        self.tokens: List[Token] = list(tokens)
        # parse the tokens into an expression tree
        self.current_context: Optional[TreeNode] = None

    @property
    def root(self) -> TreeNode:
        node = self.current_context
        while node.parent is not None:
            node = node.parent
        return node

    def parse(self):
        while len(self.tokens):
            result = self.parse_one()
            if result is None:
                raise SyntaxError(f"can't parse '{self.text}' at offset {self.tokens[0].pos}")
        root = self.root
        assert root

    def parse_one(self) -> Optional[TreeNode]:
        result = None
        for parser in [OpenBrace, BooleanAnd, BooleanOr, Compare, CloseBrace, BareVariable]:
            p = parser()
            result = p(self.tokens)
            if result is not None:
                if self.current_context is None:
                    self.current_context = result
                    break
                # we have parsed some syntax! now what?
                if isinstance(p, OpenBrace):
                    pass
                if isinstance(p, CloseBrace):
                    pass
                elif isinstance(p, Boolean):
                    # start a new expression
                    result.parent = self.current_context.parent
                    result.put(self.current_context)
                    self.current_context = result
                elif isinstance(p, BareVariable):
                    self.current_context.put(result)
                elif isinstance(p, Compare):
                    self.current_context.put(result)
                else:
                    raise SyntaxError("unknown result!")
                break

        if isinstance(p, Brace):
            if self.current_context:
                if self.current_context.op in ["(", ")"]:
                    self.current_context = self.current_context.parent

        return result

    def evaluate(self, variables: Dict[str, str]) -> bool:
        if self.tokens:
            self.parse()
        return self.evaluate_expr(self.root, variables)

    @staticmethod
    def expand_variable(text: str, variables: Dict[str, str]) -> str:
        if text.startswith("$"):
            name = text[1:]
            return variables.get(name, "")
        return text

    def evaluate_expr(self, expr: TreeNode, variables: Dict[str, str]) -> bool:
        if expr.op == "defined":
            value = self.expand_variable(expr.left.value, variables)
            if value:
                return True
        elif expr.op in ["==", "!="]:
            lhs = self.expand_variable(expr.left.text, variables)
            rhs = self.expand_variable(expr.right.text, variables)
            if expr.op == "==":
                return lhs == rhs
            return lhs != rhs
        elif expr.op in ["=~", "!~"]:
            lhs = self.expand_variable(expr.left.text, variables)
            rhs = self.expand_variable(expr.right.value, variables)
            if rhs.startswith("/"):
                rhs = re.compile(rhs[1:-1])
                match = rhs.search(lhs)
                if expr.op == "=~":
                    return match is not None
                return match is None
            elif rhs != "":
                raise SyntaxError(f"variable {expr.right.value} expanded to an invalid regex '{rhs}' at offset {expr.right.pos}")
        elif expr.op in ["||", "&&"]:
            lhs = self.evaluate_expr(expr.left, variables)
            rhs = self.evaluate_expr(expr.right, variables)
            if expr.op == "&&":
                return lhs and rhs
            return lhs or rhs

        return False


class RuleParser:
    def parse(self, text: str) -> Rule:
        token_parser = Parser()
        tokens = token_parser.parse(text)
        rule = Rule(text, tokens)
        rule.parse()
        return rule


