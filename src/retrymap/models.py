"""Data models and policy definitions for retrymap."""

from __future__ import annotations

import dataclasses
from typing import Any
from collections.abc import Callable


@dataclasses.dataclass(frozen=True)
class ExponentialPolicy:
    """Exponential backoff with optional full jitter.

    Wait = min(cap, base * 2 ** (attempt - 1)). When ``jitter=True`` the
    actual wait is drawn uniformly from [0, wait].
    """

    base: float = 1.0
    cap: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.base <= 0:
            raise ValueError("base must be positive")
        if self.cap < self.base:
            raise ValueError("cap must be >= base")
        if self.multiplier <= 0:
            raise ValueError("multiplier must be positive")


@dataclasses.dataclass(frozen=True)
class ConstantPolicy:
    """Constant backoff: wait the same ``interval`` between attempts."""

    interval: float = 1.0
    jitter: bool = False

    def __post_init__(self) -> None:
        if self.interval <= 0:
            raise ValueError("interval must be positive")


@dataclasses.dataclass(frozen=True)
class LinearPolicy:
    """Linear backoff: wait = increment * attempt."""

    increment: float = 1.0
    cap: float = 60.0
    jitter: bool = False

    def __post_init__(self) -> None:
        if self.increment <= 0:
            raise ValueError("increment must be positive")
        if self.cap < self.increment:
            raise ValueError("cap must be >= increment")


@dataclasses.dataclass(frozen=True)
class NoRetryPolicy:
    """Run once; never retry. Useful as a documented explicit choice."""


Policy = ExponentialPolicy | ConstantPolicy | LinearPolicy | NoRetryPolicy


@dataclasses.dataclass(frozen=True)
class RetryRecord:
    """Outcome of a single attempt inside a retry sequence."""

    attempt: int
    elapsed: float
    success: bool
    error: BaseException | None = None


@dataclasses.dataclass
class RetryStats:
    """Aggregate statistics for one retry sequence."""

    attempts: list[RetryRecord] = dataclasses.field(default_factory=list)
    retries: int = 0
    total_elapsed: float = 0.0
    total_wait: float = 0.0

    def add(self, record: RetryRecord, wait: float = 0.0) -> None:
        self.attempts.append(record)
        if not record.success:
            self.retries += 1
        self.total_elapsed += record.elapsed
        self.total_wait += wait

    @property
    def success(self) -> bool:
        return bool(self.attempts and self.attempts[-1].success)


@dataclasses.dataclass(frozen=True)
class RetryConfig:
    """Full configuration for a retry sequence.

    ``max_attempts`` includes the first try. ``retry_on`` accepts an exception
    or a predicate; ``do_not_retry`` always wins over ``retry_on``.
    ``total_deadline`` bounds the wall-clock budget across all attempts.
    """

    policy: Policy = dataclasses.field(default_factory=ExponentialPolicy)
    max_attempts: int = 3
    retry_on: type[BaseException] | Callable[[BaseException], bool] | None = Exception
    do_not_retry: type[BaseException] | Callable[[BaseException], bool] | None = None
    total_deadline: float | None = None

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.total_deadline is not None and self.total_deadline <= 0:
            raise ValueError("total_deadline must be positive")


@dataclasses.dataclass(frozen=True)
class Experiment:
    """A documented retry experiment.

    Stores the hypothesis, the measured parameters, and the observed outcome
    so decisions can be audited instead of re-litigated.
    """

    name: str
    hypothesis: str
    parameters: dict[str, Any]
    result: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("experiment name must not be empty")
