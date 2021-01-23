"""
Base error types
"""


class GitlabEmulatorError(Exception):
    """
    Common base for all errors we raise
    """
    pass


class DockerExecError(GitlabEmulatorError):
    """
    Docker exec failed to start
    """
    pass