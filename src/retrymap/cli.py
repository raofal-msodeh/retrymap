"""CLI for exercising retrymap policies without writing code."""

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
