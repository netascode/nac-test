# Copyright: (c) 2025, Daniel Schmidt <danischm@cisco.com>

"""Custom exception classes for nac-test."""


class NacTestError(Exception):
    """Base class for all nac-test exceptions."""
    pass


class TemplateError(NacTestError):
    """Raised when there's an error with template processing."""
    pass


class DataError(NacTestError):
    """Raised when there's an error with data files."""
    pass


class OutputError(NacTestError):
    """Raised when there's an error with output directory operations."""
    pass


class RobotExecutionError(NacTestError):
    """Raised when Robot Framework execution fails."""
    pass


class FilterError(NacTestError):
    """Raised when there's an error with Jinja filters."""
    pass


class TestError(NacTestError):
    """Raised when there's an error with Jinja tests."""
    pass