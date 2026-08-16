"""Core retry engine for retrymap."""

from __future__ import annotations

import random
import time
from typing import Any
from collections.abc import Callable

from retrymap.errors import MaxAttemptsError, PolicyError, WaitExceededError
from retrymap.models import (
    ConstantPolicy,
    ExponentialPolicy,
    LinearPolicy,
    NoRetryPolicy,
    Policy,
    RetryConfig,
    RetryRecord,
    RetryStats,
)


def compute_wait(policy: Policy, attempt: int, rng: random.Random | None = None) -> float:
    """Deterministic (up to jitter) wait before ``attempt`` (1-based)."""
    random_ref = rng if rng is not None else random
    if isinstance(policy, NoRetryPolicy):
        return 0.0
    if isinstance(policy, ExponentialPolicy):
        raw = min(policy.cap, policy.base * policy.multiplier ** (attempt - 1))
        return random_ref.uniform(0, raw) if policy.jitter else raw
    if isinstance(policy, ConstantPolicy):
        raw = policy.interval
        return random_ref.uniform(0, raw) if policy.jitter else raw
    if isinstance(policy, LinearPolicy):
        raw = min(policy.cap, policy.increment * attempt)
        return random_ref.uniform(0, raw) if policy.jitter else raw
    raise PolicyError(f"unsupported policy: {type(policy).__name__}")


def _matches(
    exc: BaseException, matcher: type[BaseException] | Callable[[BaseException], bool] | None
) -> bool:
    if matcher is None:
        return False
    if isinstance(matcher, type):
        return isinstance(exc, matcher)
    try:
        return bool(matcher(exc))
    except Exception:
        return False


def retry_call(
    fn: Callable[[], Any],
    config: RetryConfig | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Execute ``fn`` with the retry policy. Returns the successful value.

    Raises ``MaxAttemptsError`` when the budget is exhausted, carrying every
    underlying exception in ``.attempts``.
    """
    if config is None:
        config = RetryConfig()

    stats = RetryStats()
    deadline = None if config.total_deadline is None else time.monotonic() + config.total_deadline
    attempts = config.max_attempts
    rng = random.Random()

    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            result = fn()
            elapsed = time.monotonic() - started
            stats.add(RetryRecord(attempt=attempt, elapsed=elapsed, success=True))
            return result
        except BaseException as exc:
            elapsed = time.monotonic() - started
            if (
                not isinstance(config.policy, NoRetryPolicy)
                and not _matches(exc, config.do_not_retry)
                and _matches(exc, config.retry_on)
                and attempt < attempts
            ):
                wait = compute_wait(config.policy, attempt, rng)
                if deadline is not None and time.monotonic() + wait > deadline:
                    stats.add(
                        RetryRecord(attempt=attempt, elapsed=elapsed, success=False, error=exc)
                    )
                    raise WaitExceededError(
                        f"next wait ({wait:.3f}s) would exceed total deadline"
                    ) from exc
                sleep(wait)
                stats.add(
                    RetryRecord(attempt=attempt, elapsed=elapsed, success=False, error=exc),
                    wait=wait,
                )
                continue
            elapsed = time.monotonic() - started
            stats.add(RetryRecord(attempt=attempt, elapsed=elapsed, success=False, error=exc))
            if config.do_not_retry is not None and _matches(exc, config.do_not_retry):
                raise
            raise MaxAttemptsError(
                f"all {attempts} attempts exhausted",
                attempts=[r.error for r in stats.attempts],
            ) from exc
    raise MaxAttemptsError(  # pragma: no cover - attempts >= 1 guarantees a raise path
        "unreachable: loop always raises",
        attempts=[r.error for r in stats.attempts],
    )


def retryable(
    policy: Policy | None = None,
    max_attempts: int = 3,
    retry_on: type[BaseException] | Callable[[BaseException], bool] | None = Exception,
    do_not_retry: type[BaseException] | Callable[[BaseException], bool] | None = None,
    total_deadline: float | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator form of ``retry_call``."""
    config = RetryConfig(
        policy=policy if policy is not None else ExponentialPolicy(),
        max_attempts=max_attempts,
        retry_on=retry_on,
        do_not_retry=do_not_retry,
        total_deadline=total_deadline,
    )

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return retry_call(lambda: fn(*args, **kwargs), config=config)

        import typing as _typing

        _typing.cast(Any, wrapper).__wrapped__ = fn
        return wrapper

    return decorator
