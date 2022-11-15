"""Parse rules

Partly guided and inspired by https://jayconrod.com/posts/38/a-simple-interpreter-from-scratch-in-python-part-2
"""
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

class BooleanAnd(Parser):
    op = "&&"

    def __call__(self, tokens: List[Token]) -> Optional[TreeNode]:
        if len(tokens) > 0:
            if tokens[0].value == self.op:
                result = TreeNode()
                result.op = tokens.pop(0).value
                return result
        return None


class BooleanOr(BooleanAnd):
    op = "||"


class OpenBrace(Parser):
    brace = "("

    def __call__(self, tokens: List[Token]) -> Optional[TreeNode]:
        if len(tokens) > 0:
            if tokens[0].value == self.brace:
                result = TreeNode()
                result.op = "expr"
                tokens.pop(0)
                return result
        return None


class CloseBrace(OpenBrace):
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
        self.current_context: Optional[TreeNode] = TreeNode()
        self.current_context.op = "expr"

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
                # we have parsed some syntax! now what?
                if self.current_context.op == "expr":
                    if not self.current_context.left:
                        # collapse upwards
                        self.current_context = result
                        break

                if isinstance(p, CloseBrace):
                    # if the current expression has no operator the result can be collapsed into it's parent
                    #
                    # ie, the expression is:
                    #   '($foo == "x")'
                    # it becomes:
                    #   $foo == "x"
                    parent = self.current_context.parent
                    if self.current_context.op == "expr":
                        assert self.current_context.left
                        assert not self.current_context.right

                        self.current_context = self.current_context.left
                        self.current_context.parent = parent

                    result = self.current_context

                elif isinstance(p, OpenBrace):
                    result.parent = self.current_context
                    self.current_context.put(result)
                    self.current_context = result
                elif isinstance(p, BooleanAnd):
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

        # if we closed an expression and braces are redundant, collapse upwards



        return result

    def evaluate(self, variables: Dict[str, str]) -> bool:
        assert False


class RuleParser:
    def parse(self, text: str) -> Rule:
        token_parser = Parser()
        tokens = token_parser.parse(text)
        rule = Rule(text, tokens)
        rule.parse()
        return rule


