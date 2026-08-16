# RetryMap

Composable retry policies for Python with deterministic scheduling, deadline
budgets, and documented experiments. Zero runtime dependencies; Python 3.11+.

## Why

Naive retries cause production outages: linear backoff without a cap burns
resources during long outages, synchronized retries create thundering herds,
and undocumented policy choices erode under code review. [AWS's research on
exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
shows that jitter alone can cut retry load dramatically, while [Google SRE
recommends retry budgets and deadlines](https://sre.google/workbook/retry-budgets/).
Existing libraries (tenacity, backoff) are decorator-only and hard to test
deterministically; RetryMap makes the schedule itself a first-class,
computable object.

## Install

```bash
pip install dist/retrymap-1.0.0-py3-none-any.whl
# or, for development:
pip install -e ".[dev]"
```

## Usage

### Compute the schedule deterministically

```python
from retrymap import ExponentialPolicy
from retrymap.engine import compute_wait

policy = ExponentialPolicy(base=1.0, cap=60.0, jitter=False)
schedule = [compute_wait(policy, a) for a in range(1, 6)]
# [1.0, 2.0, 4.0, 8.0, 16.0]
```

The same function accepts a seeded `random.Random` when jitter is enabled,
which makes retry timing fully reproducible in tests.

### Retry a function

```python
from retrymap import ExponentialPolicy, RetryConfig, retry_call

def flaky_service() -> str:
    return requests.get("https://api.example.com/data").text

result = retry_call(
    flaky_service,
    config=RetryConfig(
        policy=ExponentialPolicy(base=1.0, cap=30.0),
        max_attempts=5,
        retry_on=ConnectionError,
        do_not_retry=ValueError,   # always wins over retry_on
        total_deadline=60.0,       # wall-clock budget across all attempts
    ),
)
```

On exhaustion, `retry_call` raises `MaxAttemptsError`, carrying every
underlying exception in `.attempts` so failures can be logged and audited.
When the next wait would violate `total_deadline`, it raises
`WaitExceededError` instead.

### Decorator form

```python
from retrymap import retryable, LinearPolicy

@retryable(policy=LinearPolicy(increment=2.0), max_attempts=4)
def push_metrics(payload: dict) -> None:
    ...
```

### Dry-run a policy from the shell

```bash
python3 -m retrymap exponential --base 1 --cap 32 --attempts 5 --no-jitter
# schedule: [1.0, 2.0, 4.0, 8.0, 16.0]  total_wait: 31.0
```

### Document the decision

```python
from retrymap.models import Experiment

Experiment(
    name="jitter-storm",
    hypothesis="full jitter halves peak load during partial outages",
    parameters={"base": 1.0, "cap": 60.0, "jitter": True},
    result={"observed_peak": 0.5},
)
```

## Comparison with alternatives

| Feature | tenacity | backoff | pybackoff | **retrymap** |
| --- | --- | --- | --- | --- |
| Deterministic wait schedule (`compute_wait`) | Partial | No | No | Yes |
| Injectable sleep for testing | Via mock | Partial | No | Yes (`sleep=` param) |
| Seedable jitter RNG | No | No | No | Yes |
| Predicate-based `retry_on` / `do_not_retry` | Partial | No | No | Yes |
| Wall-clock deadline | Partial | No | No | Yes (`total_deadline`) |
| Documented experiments | No | No | No | Yes (`Experiment`) |
| Runtime dependencies | Yes | No | No | **None** |

## Exit conventions and error hierarchy

All errors derive from `RetryError`. `MaxAttemptsError.attempts` carries the
full exception history; `PolicyError` covers invalid policy parameters;
`WaitExceededError` covers deadline breaches. There is no CLI process, so no
exit codes; the library signals through exceptions only.

## Development

```bash
pip install -e ".[dev]"
make quality   # ruff + mypy
make test      # pytest
make build     # wheel + sdist
make example   # python3 -m retrymap exponential --no-jitter
make redteam   # scripts/red_team.sh
```

CI is defined in `docs/ci-workflow.yml` (GitHub Actions; the release token
lacks `workflows` permissions, so the workflow lives outside `.github/`).

## Security

No network, no subprocess, no filesystem access inside the library. Backoff
computation is pure arithmetic; jitter uses an isolated `random.Random`
instance. See [SECURITY.md](SECURITY.md) for reporting.

## License

MIT. See [LICENSE](LICENSE).
