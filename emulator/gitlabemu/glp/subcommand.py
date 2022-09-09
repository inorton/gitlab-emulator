"""Base classes for subcommands"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Optional
from .types import Match, RefMatch


class ArgumentParserEx(ArgumentParser):
    """An ArgumentParser where subparsers is accessible"""

    def __init__(self, **kwargs):
        super(ArgumentParserEx, self).__init__(**kwargs)
        self._commands = None

    def add_subcommand(self, command: "Command"):
        if self._commands is None:
            self._commands = self.add_subparsers(title="subcommands", help="additional help")
        command.register(self)

    @property
    def commands(self):
        return self._commands


class Command(ABC):
    def __init__(self):
        self.parser: Optional[ArgumentParser] = None
        self.parent: Optional[ArgumentParserEx] = None

    def register(self, parser: ArgumentParserEx):
        self.parser = parser.commands.add_parser(self.name, description=self.description)
        self.setup(self.parser)
        self.parser.set_defaults(func=self.run)

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def setup(self, parser: ArgumentParser) -> None:
        pass

    @abstractmethod
    def run(self, opts: Namespace):
        pass


class MatcherCommand(Command, ABC):
    def setup(self, parser: ArgumentParser) -> None:
        parser.add_argument("--match",
                            dest="match",
                            type=Match,
                            action="append",
                            default=[],
                            help="Filter pipelines by status/ref")
        parser.add_argument("--ref",
                            metavar="REFERENCE",
                            dest="match",
                            type=RefMatch,
                            action="append",
                            help="Filter pipelines by ref (shortcut for --match ref=REFERENCE")
        parser.add_argument("--limit",
                            type=int,
                            default=10,
                            metavar="COUNT",
                            help="Include up to COUNT results")
