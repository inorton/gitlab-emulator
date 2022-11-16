"""Parse gitlab rule expression strings into lexical tokens"""
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional


WHITESPACE = " \t\r\n"

class TokenClass(Enum):
    TEXT = auto()
    BRACE = auto()


class Token:
    def __init__(self):
        self.value: str = ""
        self.pos: int = 0
        self.complete = False
        self.quoted = False

    @property
    def text(self):
        if self.quoted:
            return self.value[1:-1]
        return self.value

    def __len__(self) -> int:
        return len(self.value)

    def __repr__(self):
        suffix = ""
        if not self.complete:
            suffix = " (incomplete)"
        return f"Token [{self.value}]{suffix}"

    def __str__(self):
        return str(self.value)

    @property
    def first(self) -> str:
        if len(self.value):
            return self.value[0]
        raise ValueError()


class Parser:
    def __init__(self):
        self.tokens: List[Token] = []
        self.state: Optional[ParserState] = None
        self.text = ""
        self._len = 0
        self._pos = 0

    def __repr__(self):  # pragma: no cover
        return f"Parser, remaining: [{self.text[self._pos:]}]"

    @property
    def eof(self) -> bool:
        return self.pos >= self._len

    @property
    def pos(self) -> int:
        return self._pos

    def peek(self) -> str:
        value = ""
        if not self.eof:
            value = self.text[self.pos]
        return value

    def advance(self) -> None:
        if not self.eof:
            self._pos += 1

    def read(self) -> str:
        value = self.peek()
        self.advance()
        return value

    def parse(self, text: str) -> List[Token]:
        self.state = ParserStateStart(self)
        self._pos = 0
        self.text = text
        self._len = len(text)

        while not self.eof:
            token = self.state.parse()
            if token:
                if not token.complete:
                    raise SyntaxError()
                self.tokens.append(token)
        return self.tokens


class ParserState(ABC):
    def __init__(self, parser: "Parser"):
        self.parser = parser

    @abstractmethod
    def parse(self) -> Optional[Token]:
        """Parse the current token, advance the parser position and return the token if any"""

    @staticmethod
    def is_whitespace(char: str) -> bool:
        result = char and char in WHITESPACE
        return result

    def skip_whitespace(self):
        while self.is_whitespace(self.parser.peek()):
            self.parser.advance()


class ParserStateText(ParserState):

    def read(self, token: Token) -> str:
        char = self.parser.read()
        token.value += char
        return char

    def parse(self) -> Optional[Token]:
        token: Optional[Token] = None
        self.skip_whitespace()
        char = self.parser.peek()
        quoted = None
        if char:
            # token stars here
            token = Token()
            token.pos = self.parser.pos
            self.read(token)
            if token.first and token.first in "'\"/":
                quoted = token.first

            while not self.parser.eof and not token.complete:
                char = self.parser.peek()
                if quoted is not None:
                    # string is in quotes, read until we see the closing quote char
                    self.read(token)

                    # gitlab doesn't support escape chars (yet)
                    #if char == "\\":
                    #    # escaped char, read the next char
                    #    self.read(token)

                    if char == quoted:
                        # end quote (also end of token)
                        token.complete = True
                        token.quoted = True
                        break
                elif char == ")":
                    token.complete = True
                elif self.is_whitespace(char):
                    # end of a non-quoted string so end of the token
                    token.complete = True
                else:
                    self.read(token)

        if token:
            if not quoted and not token.complete:
                # eof when reading a non quoted thing (last thing in the exp)
                token.complete = True

        # next token is either a ) or an operator
        if token and token.complete:
            # hoover all the whitespace
            self.skip_whitespace()
            self.parser.state = ParserStateStart(self.parser)
        return token


class ParserStateStart(ParserState):

    def parse(self) -> Optional[Token]:
        # figure out if the next token is a bracket or is text
        token: Optional[Token] = None
        self.skip_whitespace()
        char = self.parser.peek()
        if char != "":
            # start/end bracket
            if char in "()":
                token = Token()
                token.value = self.parser.read()
                token.pos = self.parser.pos
                token.complete = True
                # state remains unchanged
            else:
                # everything else
                self.parser.state = ParserStateText(self.parser)

        return token
