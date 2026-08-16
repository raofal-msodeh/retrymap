"""Full scaffold for RetryMap: config + empty module stubs + test skeleton."""
import os

BASE = "/home/ubuntu/retrymap"


def w(rel: str, content: str) -> None:
    path = os.path.join(BASE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote", rel)


# ---------- pyproject.toml ----------
w(
    "pyproject.toml",
    """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "retrymap"
version = "1.0.0"
description = "Composable retry policies with backoff, jitter, and documented experiments"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
keywords = ["retry", "backoff", "resilience", "circuit", "fault-tolerance"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries",
    "Typing :: Typed",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.4", "mypy>=1.10", "build>=1.2"]

[project.urls]
Repository = "https://github.com/raofal-msodeh/retrymap"

[tool.hatch.build.targets.wheel]
packages = ["src/retrymap"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "B", "UP", "RUF", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_ignores = true
exclude = ["^tests/"]
""",
)

# ---------- module stubs ----------
w(
    "src/retrymap/__init__.py",
    '''"""RetryMap: composable retry policies with backoff and experiments."""

from retrymap.errors import RetryError, PolicyError, MaxAttemptsError, WaitExceededError
from retrymap.models import (
    ExponentialPolicy,
    ConstantPolicy,
    LinearPolicy,
    NoRetryPolicy,
    Policy,
    RetryRecord,
    RetryStats,
)
from retrymap.engine import retry_call, retryable

__all__ = [
    "ExponentialPolicy",
    "ConstantPolicy",
    "LinearPolicy",
    "NoRetryPolicy",
    "Policy",
    "RetryError",
    "RetryRecord",
    "RetryStats",
    "MaxAttemptsError",
    "PolicyError",
    "WaitExceededError",
    "retry_call",
    "retryable",
]
''',
)

w(
    "src/retrymap/__main__.py",
    '''"""Allow `python3 -m retrymap` to run the demo."""
from retrymap.demo import main

raise SystemExit(main())
''',
)

w(
    "src/retrymap/errors.py",
    '''"""Typed exception hierarchy for retrymap."""

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
''',
)

w(
    "src/retrymap/models.py",
    '''"""Data models and policy definitions for retrymap."""

from __future__ import annotations

import dataclasses
from typing import Any, Callable


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
''',
)

w(
    "src/retrymap/engine.py",
    '''"""Core retry engine for retrymap."""

from __future__ import annotations

import random
import time
from typing import Any, Callable

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


def _matches(exc: BaseException, matcher: type[BaseException] | Callable[[BaseException], bool] | None) -> bool:
    if matcher is None:
        return False
    if isinstance(matcher, type):
        return isinstance(exc, matcher)
    try:
        return bool(matcher(exc))
    except Exception:  # noqa: BLE001 - predicates must never break the loop
        return False


def retry_call(fn: Callable[[], Any], config: RetryConfig | None = None, sleep: Callable[[float], None] = time.sleep) -> Any:  # noqa: C901
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
            stats._config = config  # type: ignore[attr-defined]
            return result
        except BaseException as exc:  # noqa: BLE001
            elapsed = time.monotonic() - started
            if not _matches(exc, config.do_not_retry) and _matches(exc, config.retry_on) and attempt < attempts:
                wait = compute_wait(config.policy, attempt, rng)
                if deadline is not None and time.monotonic() + wait > deadline:
                    stats.add(RetryRecord(attempt=attempt, elapsed=elapsed, success=False, error=exc))
                    raise WaitExceededError(
                        f"next wait ({wait:.3f}s) would exceed total deadline"
                    ) from exc
                sleep(wait)
                stats.add(RetryRecord(attempt=attempt, elapsed=elapsed, success=False, error=exc), wait=wait)
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

        wrapper.__wrapped__ = fn
        return wrapper

    return decorator
''',
)

w(
    "src/retrymap/demo.py",
    '''"""Demonstration of retrymap policies."""

import random

from retrymap.engine import compute_wait, retry_call
from retrymap.models import ExponentialPolicy, RetryConfig


def main() -> int:
    flaky_state = {"tries": 0}

    def flaky() -> str:
        flaky_state["tries"] += 1
        if flaky_state["tries"] < 3:
            raise ConnectionError("flaky service")
        return "connected"

    config = RetryConfig(
        policy=ExponentialPolicy(base=0.01, jitter=False),
        max_attempts=5,
        sleep=lambda _s: None,  # demo: skip real sleeping
    )

    result = retry_call(flaky, config=config)
    print(f"result={result!r} after {flaky_state['tries']} attempts")

    # Show the wait schedule
    policy = ExponentialPolicy(base=1.0, cap=32.0, jitter=False)
    waits = [compute_wait(policy, a) for a in range(1, 6)]
    print("exponential waits:", waits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
)

w(
    "src/retrymap/cli.py",
    '''"""CLI for exercising retrymap policies without writing code."""

from __future__ import annotations

from typing import Any

from retrymap.engine import compute_wait
from retrymap.errors import PolicyError
from retrymap.models import ConstantPolicy, ExponentialPolicy, LinearPolicy, Policy


def _parse_policy(name: str, base: float, cap: float, jitter: bool) -> Policy:
    if name == "exponential":
        return ExponentialPolicy(base=base, cap=cap, jitter=jitter)
    if name == "constant":
        return ConstantPolicy(interval=base, jitter=jitter)
    if name == "linear":
        return LinearPolicy(increment=base, cap=cap, jitter=jitter)
    raise PolicyError(f"unknown policy: {name}")


def _usage() -> str:
    return (
        "usage: python3 -m retrymap <policy> [--base N] [--cap N] [--attempts N] [--no-jitter]\n"
        "  policies: exponential | constant | linear\n"
    )


def main(argv: list[str] | None = None) -> int:
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(_usage())
        return 0 if args else 2
    name = args[0]
    base, cap, attempts, jitter = 1.0, 60.0, 5, True
    it = iter(args[1:])
    for token in it:
        if token == "--base":
            base = float(next(it))
        elif token == "--cap":
            cap = float(next(it))
        elif token == "--attempts":
            attempts = int(next(it))
        elif token == "--no-jitter":
            jitter = False
        else:
            print(f"error: unknown option {token}", flush=True)
            return 2
    try:
        policy = _parse_policy(name, base, cap, jitter)
    except (PolicyError, ValueError) as exc:
        print(f"error: {exc}", flush=True)
        return 2
    if jitter:
        print("jitter-enabled waits are stochastic; use --no-jitter for a fixed schedule")
        return 0
    schedule: list[Any] = [compute_wait(policy, a) for a in range(1, attempts + 1)]
    print("policy:", name)
    print("base:", base, "cap:", cap, "attempts:", attempts)
    print("schedule:", [round(w, 3) for w in schedule])
    print("total_wait:", round(sum(schedule), 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
)

# ---------- __main__ points at cli now ----------
w(
    "src/retrymap/__main__.py",
    '''"""Allow `python3 -m retrymap` to run the CLI."""
from retrymap.cli import main

raise SystemExit(main())
''',
)

# ---------- test skeleton ----------
w(
    "tests/__init__.py",
    "",
)

print("scaffold complete")
