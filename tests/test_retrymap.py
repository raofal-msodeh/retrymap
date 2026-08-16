"""Comprehensive test suite for retrymap."""

from __future__ import annotations

import random

import pytest

from retrymap import (
    ConstantPolicy,
    ExponentialPolicy,
    LinearPolicy,
    MaxAttemptsError,
    NoRetryPolicy,
    PolicyError,
    RetryConfig,
    RetryError,
    WaitExceededError,
    retry_call,
    retryable,
)
from retrymap.engine import compute_wait
from retrymap.models import Experiment


# ----------------------------------------------------------------- policy validation


def test_exponential_policy_rejects_invalid_base() -> None:
    with pytest.raises(ValueError):
        ExponentialPolicy(base=0)  # type: ignore[arg-type]


def test_exponential_policy_rejects_cap_below_base() -> None:
    with pytest.raises(ValueError):
        ExponentialPolicy(base=2.0, cap=1.0)


def test_linear_policy_rejects_invalid_increment() -> None:
    with pytest.raises(ValueError):
        LinearPolicy(increment=-1)  # type: ignore[arg-type]


def test_constant_policy_rejects_nonpositive_interval() -> None:
    with pytest.raises(ValueError):
        ConstantPolicy(interval=0)  # type: ignore[arg-type]


# ----------------------------------------------------------------- compute_wait


def test_exponential_schedule_without_jitter() -> None:
    policy = ExponentialPolicy(base=1.0, cap=64.0, multiplier=2.0, jitter=False)
    expected = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 64.0]
    actual = [compute_wait(policy, a) for a in range(1, 9)]
    assert actual == expected


def test_exponential_with_custom_multiplier() -> None:
    policy = ExponentialPolicy(base=2.0, multiplier=3.0, cap=100.0, jitter=False)
    assert compute_wait(policy, 3) == 18.0  # 2 * 3^2


def test_linear_schedule() -> None:
    policy = LinearPolicy(increment=1.0, cap=3.0, jitter=False)
    assert [compute_wait(policy, a) for a in range(1, 5)] == [1.0, 2.0, 3.0, 3.0]


def test_constant_wait() -> None:
    policy = ConstantPolicy(interval=2.5, jitter=False)
    assert all(compute_wait(policy, a) == 2.5 for a in range(1, 10))


def test_no_retry_policy_waits_zero() -> None:
    assert compute_wait(NoRetryPolicy(), 1) == 0.0


def test_unsupported_policy_raises() -> None:
    with pytest.raises(PolicyError):
        compute_wait(object(), 1)  # type: ignore[arg-type]


def test_jitter_bounded() -> None:
    rng = random.Random(7)
    policy = ExponentialPolicy(base=1.0, cap=8.0, jitter=True)
    for attempt in range(1, 20):
        wait = compute_wait(policy, attempt, rng)
        raw = min(8.0, 2 ** (attempt - 1))
        assert 0.0 <= wait <= raw


def test_jitter_reproducible_with_seed() -> None:
    rng1 = random.Random(123)
    rng2 = random.Random(123)
    policy = ExponentialPolicy(jitter=True)
    a = [compute_wait(policy, i, rng1) for i in range(1, 5)]
    b = [compute_wait(policy, i, rng2) for i in range(1, 5)]
    assert a == b


# ----------------------------------------------------------------- retry_call


def test_immediate_success() -> None:
    result = retry_call(lambda: "ok", RetryConfig(), sleep=lambda _s: None)
    assert result == "ok"


def test_recovers_after_failures() -> None:
    state: dict[str, int] = {"n": 0}

    def flaky() -> str:
        state["n"] += 1
        if state["n"] < 3:
            raise ConnectionError("flaky")
        return "connected"

    sleeps: list[float] = []
    cfg = RetryConfig(
        policy=ExponentialPolicy(base=0.1, cap=1.0, jitter=False),
        max_attempts=5,
        retry_on=ConnectionError,
    )
    assert retry_call(flaky, config=cfg, sleep=sleeps.append) == "connected"
    assert state["n"] == 3
    assert sleeps == [0.1, 0.2]


def test_max_attempts_exhausted() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise ValueError("boom")

    with pytest.raises(MaxAttemptsError) as exc_info:
        retry_call(
            fails,
            RetryConfig(max_attempts=2, retry_on=Exception),
            sleep=lambda _s: None,
        )
    assert len(exc_info.value.attempts) == 2
    assert state["n"] == 2


def test_no_retry_policy_single_attempt() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise RuntimeError("nope")

    with pytest.raises(MaxAttemptsError):
        retry_call(fails, RetryConfig(policy=NoRetryPolicy()), sleep=lambda _s: None)
    assert state["n"] == 1


def test_do_not_retry_type_wins() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise KeyError("missing")

    with pytest.raises(KeyError):
        retry_call(
            fails,
            RetryConfig(max_attempts=3, retry_on=Exception, do_not_retry=KeyError),
            sleep=lambda _s: None,
        )
    assert state["n"] == 1


def test_do_not_retry_predicate_wins() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise PermissionError("denied")

    with pytest.raises(PermissionError):
        retry_call(
            fails,
            RetryConfig(
                max_attempts=3,
                retry_on=Exception,
                do_not_retry=lambda e: isinstance(e, PermissionError),
            ),
            sleep=lambda _s: None,
        )
    assert state["n"] == 1


def test_retry_on_predicate() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise ValueError(state["n"])

    # retry only when the counter is odd
    cfg = RetryConfig(
        max_attempts=4,
        retry_on=lambda e: isinstance(e, ValueError) and e.args[0] % 2 == 1,
    )
    with pytest.raises(MaxAttemptsError):
        retry_call(fails, cfg, sleep=lambda _s: None)
    assert state["n"] == 2  # attempt 1 (value=1, retry), attempt 2 (value=2, stop)


def test_retry_on_none_never_retries() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise RuntimeError("x")

    with pytest.raises(MaxAttemptsError):
        retry_call(fails, RetryConfig(max_attempts=5, retry_on=None), sleep=lambda _s: None)
    assert state["n"] == 1


def test_predicate_exception_never_breaks_loop() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise RuntimeError("x")

    def bad_predicate(_: BaseException) -> bool:
        raise TypeError("predicate itself is broken")

    with pytest.raises(MaxAttemptsError):
        retry_call(
            fails,
            RetryConfig(max_attempts=2, retry_on=bad_predicate),  # type: ignore[arg-type]
            sleep=lambda _s: None,
        )
    assert state["n"] == 1  # broken predicate never matches; single attempt then MaxAttemptsError


def test_non_retryable_exception_raises_directly() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise TimeoutError("not retryable")

    with pytest.raises(MaxAttemptsError):
        retry_call(
            fails,
            RetryConfig(max_attempts=3, retry_on=ConnectionError),
            sleep=lambda _s: None,
        )
    assert state["n"] == 1


def test_total_deadline_raises_wait_exceeded() -> None:
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise RuntimeError("slow")

    with pytest.raises(WaitExceededError):
        retry_call(
            fails,
            RetryConfig(
                policy=ExponentialPolicy(base=10.0, jitter=False),
                max_attempts=5,
                retry_on=RuntimeError,
                total_deadline=1.0,
            ),
            sleep=lambda _s: None,
        )
    assert state["n"] == 1


def test_no_wait_on_final_attempt() -> None:
    """The last attempt must not sleep before raising."""
    sleeps: list[float] = []
    state: dict[str, int] = {"n": 0}

    def fails() -> None:
        state["n"] += 1
        raise ValueError("x")

    cfg = RetryConfig(
        policy=ConstantPolicy(interval=5.0, jitter=False),
        max_attempts=2,
        retry_on=Exception,
    )
    with pytest.raises(MaxAttemptsError):
        retry_call(fails, cfg, sleep=sleeps.append)
    assert sleeps == [5.0]  # one sleep between attempts, none after the final one
    assert state["n"] == 2


def test_sleep_is_called_between_attempts_only() -> None:
    sleeps: list[float] = []
    state: dict[str, int] = {"n": 0}

    def flaky() -> str:
        state["n"] += 1
        if state["n"] < 4:
            raise RuntimeError("f")
        return "done"

    cfg = RetryConfig(
        policy=ExponentialPolicy(base=1.0, jitter=False),
        max_attempts=5,
        retry_on=RuntimeError,
    )
    assert retry_call(flaky, cfg, sleep=sleeps.append) == "done"
    assert sleeps == [1.0, 2.0, 4.0]
    assert len(sleeps) == state["n"] - 1


# ----------------------------------------------------------------- retryable decorator


def test_retryable_decorator_recovers() -> None:
    state: dict[str, int] = {"n": 0}

    @retryable(policy=ConstantPolicy(interval=0.1, jitter=False), max_attempts=3)
    def flaky() -> str:
        state["n"] += 1
        if state["n"] < 2:
            raise ConnectionError("f")
        return "ok"

    assert flaky() == "ok"
    assert state["n"] == 2


def test_retryable_preserves_wrapped_reference() -> None:
    def fn() -> None:
        return None

    wrapped = retryable()(fn)
    assert getattr(wrapped, "__wrapped__", None) is fn


# ----------------------------------------------------------------- experiment


def test_experiment_requires_name() -> None:
    with pytest.raises(ValueError):
        Experiment(name="", hypothesis="h", parameters={})


def test_experiment_roundtrip() -> None:
    exp = Experiment(
        name="jitter-storm",
        hypothesis="full jitter halves peak load",
        parameters={"base": 1.0, "cap": 60.0},
        result={"observed_peak": 0.5},
    )
    assert exp.result["observed_peak"] == 0.5


# ----------------------------------------------------------------- retry_config validation


def test_config_rejects_zero_attempts() -> None:
    with pytest.raises(ValueError):
        RetryConfig(max_attempts=0)


def test_config_rejects_negative_deadline() -> None:
    with pytest.raises(ValueError):
        RetryConfig(total_deadline=-1.0)


def test_config_default_policy() -> None:
    cfg = RetryConfig()
    assert isinstance(cfg.policy, ExponentialPolicy)


# ----------------------------------------------------------------- error hierarchy


def test_errors_inherit_from_retry_error() -> None:
    assert issubclass(MaxAttemptsError, RetryError)
    assert issubclass(WaitExceededError, RetryError)
    assert issubclass(PolicyError, RetryError)


def test_max_attempts_error_carries_exceptions() -> None:
    exc = MaxAttemptsError("x", attempts=[ValueError("a"), ValueError("b")])
    assert len(exc.attempts) == 2
    assert exc.args[0] == "x"
