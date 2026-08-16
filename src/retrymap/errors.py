"""Typed exception hierarchy for retrymap."""

from __future__ import annotations

from typing import Any


class RetryError(Exception):
    """Base class for all retry-related errors."""


class PolicyError(RetryError):
    """Raised when a policy configuration is invalid."""


class MaxAttemptsError(RetryError):
    """Raised when the attempt budget is exhausted.

    Carries the underlying exceptions so callers can inspect the full history.
    """

    def __init__(self, message: str, attempts: list[Any]) -> None:
        super().__init__(message)
        self.attempts = attempts


class WaitExceededError(RetryError):
    """Raised when a computed wait time exceeds the policy deadline."""
