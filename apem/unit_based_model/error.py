"""
Shared error type used across unit-based allocation, redispatch, and pricing.
"""


class Error(Exception):
    """
    Lightweight status-carrying error object returned by solver routines.

    :param status: numeric status code describing the failure condition
    """

    def __init__(self, status):
        self._status = status

    @property
    def status(self):
        """
        Return the stored failure status code.
        """
        return self._status
