"""Quick smoke test of retrymap core."""
import random
import sys

sys.path.insert(0, "/home/ubuntu/retrymap/src")

from retrymap.engine import compute_wait, retry_call
from retrymap.models import ExponentialPolicy, RetryConfig, RetryStats

# 1. deterministic wait schedule
policy = ExponentialPolicy(base=1.0, cap=16.0, jitter=False)
waits = [compute_wait(policy, a) for a in range(1, 6)]
print("waits:", waits)
assert waits == [1.0, 2.0, 4.0, 8.0, 16.0], waits

# 2. jitter bounded
rng = random.Random(42)
for a in range(1, 10):
    w = compute_wait(policy, a, rng)
    expected_raw = min(16.0, 2 ** (a - 1))
    assert 0 <= w <= expected_raw, (a, w)
print("jitter bounded: ok")

# 3. success after failures with injected sleep
state = {"n": 0}

def flaky():
    state["n"] += 1
    if state["n"] < 3:
        raise ConnectionError("flaky")
    return "ok"

sleeps: list[float] = []
cfg = RetryConfig(
    policy=ExponentialPolicy(base=0.1, cap=1.0, jitter=False),
    max_attempts=5,
    retry_on=ConnectionError,
)
result = retry_call(flaky, config=cfg, sleep=sleeps.append)
print("result:", result, "attempts:", state["n"], "sleeps:", sleeps)
assert result == "ok" and state["n"] == 3
assert len(sleeps) == 2
assert sleeps == [0.1, 0.2], sleeps

# 4. max attempts exhaustion
state["n"] = 0

def always_fails():
    state["n"] += 1
    raise ValueError("boom")

try:
    retry_call(always_fails, config=RetryConfig(max_attempts=2, retry_on=Exception), sleep=lambda _s: None)
except Exception as exc:  # noqa: BLE001
    from retrymap.errors import MaxAttemptsError
    assert isinstance(exc, MaxAttemptsError), type(exc)
    assert len(exc.attempts) == 2, exc.attempts
    print("MaxAttemptsError ok:", exc.attempts)

# 5. do_not_retry
state["n"] = 0

def fails_once_with_key():
    state["n"] += 1
    raise KeyError("missing")

try:
    retry_call(
        fails_once_with_key,
        config=RetryConfig(max_attempts=3, retry_on=Exception, do_not_retry=KeyError),
        sleep=lambda _s: None,
    )
except KeyError:
    assert state["n"] == 1
    print("do_not_retry ok")

# 6. deadline
from retrymap.errors import WaitExceededError
try:
    retry_call(
        always_fails,
        config=RetryConfig(
            policy=ExponentialPolicy(base=10.0, jitter=False),
            max_attempts=5,
            retry_on=Exception,
            total_deadline=1.0,
        ),
        sleep=lambda _s: None,
    )
except WaitExceededError:
    print("deadline ok")

print("ALL SMOKE TESTS PASSED")
