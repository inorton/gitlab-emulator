"""Base and useful classes"""
from abc import ABC, abstractmethod
from typing import List

from gitlabemu.errors import GitlabEmulatorError

class BaseJob(ABC):
    """Base class for all CI jobs returned by a loader"""

    @abstractmethod
    def duration(self) -> int:
        pass

    @property
    @abstractmethod
    def dependencies(self) -> List[str]:
        pass


class BaseLoader(ABC):
    """Base class for all CI loaders"""

    @abstractmethod
    def do_validate(self, baseobj) -> None:
        pass

    @abstractmethod
    def get_jobs(self) -> List[str]:
        pass

    @abstractmethod
    def get_job(self, name) -> dict:
        pass

    @abstractmethod
    def load_job(self, name) -> BaseJob:
        pass

    @property
    @abstractmethod
    def config(self) -> dict:
        pass


class ConfigLoaderError(GitlabEmulatorError):
    """
    There was an error loading a configuration
    """
    pass


class BadSyntaxError(ConfigLoaderError):
    """
    The yaml was somehow invalid
    """

    def __init__(self, message):
        super(BadSyntaxError, self).__init__(message)


class FeatureNotSupportedError(ConfigLoaderError):
    """
    The loaded configuration contained gitlab features we do not
    yet support
    """

    def __init__(self, feature):
        self.feature = feature

    def __str__(self):
        return "FeatureNotSupportedError ({})".format(self.feature)
