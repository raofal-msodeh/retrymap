#!/usr/bin/env bash
# RetryMap red-team harness: hostile inputs must be rejected or handled safely.
set -u
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

PASS=0
FAIL=0

check() {
    local name="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "PASS: $name"
        PASS=$((PASS + 1))
    else
        echo "FAIL: $name"
        FAIL=$((FAIL + 1))
    fi
}

check_fail() {
    local name="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "FAIL: $name (should have raised/exited nonzero)"
        FAIL=$((FAIL + 1))
    else
        echo "PASS: $name"
        PASS=$((PASS + 1))
    fi
}

# 1. invalid policy parameters must raise ValueError at construction time
check_fail "policy: base=0 rejected" \
    python3 -c "from retrymap import ExponentialPolicy; ExponentialPolicy(base=0)"

check_fail "policy: cap < base rejected" \
    python3 -c "from retrymap import ExponentialPolicy; ExponentialPolicy(base=2.0, cap=1.0)"

check_fail "policy: linear increment=0 rejected" \
    python3 -c "from retrymap import LinearPolicy; LinearPolicy(increment=0)"

# 2. invalid retry config
check_fail "config: max_attempts=0 rejected" \
    python3 -c "from retrymap import RetryConfig; RetryConfig(max_attempts=0)"

check_fail "config: negative deadline rejected" \
    python3 -c "from retrymap import RetryConfig; RetryConfig(total_deadline=-1.0)"

# 3. unknown policy name in CLI
check_fail "cli: unknown policy rejected" \
    python3 -m retrymap unknown-policy

check_fail "cli: unknown policy exits nonzero" \
    python3 -m retrymap unknown-policy

# 4. garbage CLI arguments
check_fail "cli: garbage options rejected" \
    python3 -m retrymap exponential --garbage-flag

check_fail "cli: missing option value" \
    python3 -m retrymap exponential --base

# 5. deadline enforcement: a huge base with a tiny deadline must raise
check "deadline: WaitExceededError on tiny budget" \
    python3 -c "
from retrymap import ExponentialPolicy, RetryConfig, retry_call
from retrymap.errors import WaitExceededError
def fails():
    raise RuntimeError('x')
try:
    retry_call(fails, RetryConfig(policy=ExponentialPolicy(base=10.0, jitter=False),
              max_attempts=5, retry_on=RuntimeError, total_deadline=0.5),
              sleep=lambda s: None)
    raise AssertionError('expected WaitExceededError')
except WaitExceededError:
    pass
"

# 6. predicate that raises must never break the retry loop
check "predicate: broken predicate handled safely" \
    python3 -c "
from retrymap import RetryConfig, retry_call, MaxAttemptsError
def fails():
    raise RuntimeError('x')
def broken(_e):
    raise TypeError('broken')
try:
    retry_call(fails, RetryConfig(max_attempts=2, retry_on=broken), sleep=lambda s: None)
    raise AssertionError('expected MaxAttemptsError')
except MaxAttemptsError as e:
    assert len(e.attempts) == 1, 'single attempt when predicate never matches'
"

# 7. do_not_retry must win even when retry_on matches everything
check "do_not_retry: wins over retry_on" \
    python3 -c "
from retrymap import RetryConfig, retry_call
def fails():
    raise PermissionError('denied')
try:
    retry_call(fails, RetryConfig(max_attempts=3, retry_on=Exception,
              do_not_retry=PermissionError), sleep=lambda s: None)
    raise AssertionError('expected PermissionError')
except PermissionError:
    pass
"

# 8. exhausted attempts must carry the full exception history
check "exhaustion: carries attempt history" \
    python3 -c "
from retrymap import RetryConfig, retry_call, MaxAttemptsError
def fails():
    raise ValueError('boom')
try:
    retry_call(fails, RetryConfig(max_attempts=3, retry_on=Exception), sleep=lambda s: None)
except MaxAttemptsError as e:
    assert len(e.attempts) == 3 and all(isinstance(a, ValueError) for a in e.attempts)
"

# 9. jitter stays bounded for extreme attempts
check "jitter: bounded under cap" \
    python3 -c "
import random
from retrymap import ExponentialPolicy
from retrymap.engine import compute_wait
rng = random.Random(1)
policy = ExponentialPolicy(base=0.001, cap=60.0, jitter=True)
for a in range(1, 1000):
    w = compute_wait(policy, a, rng)
    assert 0.0 <= w <= 60.0, (a, w)
"

# 10. experiment requires a name
check_fail "experiment: empty name rejected" \
    python3 -c "from retrymap.models import Experiment; Experiment(name='', hypothesis='h', parameters={})"

# 11. retry with real failures runs end to end
check "demo: real failures recover" \
    python3 -c "
from retrymap import ExponentialPolicy, RetryConfig, retry_call
state = {'n': 0}
def flaky():
    state['n'] += 1
    if state['n'] < 3:
        raise ConnectionError('flaky')
    return 'connected'
result = retry_call(flaky, RetryConfig(policy=ExponentialPolicy(base=0.01, jitter=False), max_attempts=5, retry_on=ConnectionError), sleep=lambda s: None)
assert result == 'connected' and state['n'] == 3
"

# 12. clean CLI schedule output
check "cli: schedule output valid" \
    python3 -c "
import subprocess, json
out = subprocess.run(['python3', '-m', 'retrymap', 'exponential',
                      '--base', '1', '--cap', '32', '--attempts', '4', '--no-jitter'],
                     capture_output=True, text=True, check=True).stdout
assert '1.0' in out and '2.0' in out and '4.0' in out and '8.0' in out
"

echo
echo "red-team: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
