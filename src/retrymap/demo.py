"""Demonstration of retrymap policies."""

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
    )

    result = retry_call(flaky, config=config, sleep=lambda _s: None)  # demo: skip real sleeping
    print(f"result={result!r} after {flaky_state['tries']} attempts")

    # Show the wait schedule
    policy = ExponentialPolicy(base=1.0, cap=32.0, jitter=False)
    waits = [compute_wait(policy, a) for a in range(1, 6)]
    print("exponential waits:", waits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
