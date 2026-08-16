# ADR-0001: Deterministic scheduling with injected sleep

## Status

Accepted (2026-08-16).

## Context

Retries are inherently time-dependent, which makes them hard to test and
review: decorator-only libraries force mocking of `time.sleep` at the
boundary, and schedules cannot be inspected without running the loop.

## Decision

Split scheduling from execution:

- `compute_wait(policy, attempt, rng=None)` is a pure, deterministic function.
- `retry_call(fn, config, sleep=time.sleep)` separates *what* to wait from
  *how* time passes. Jitter uses an isolated seeded `random.Random`, never
  global state.

## Consequences

- Schedules can be printed, tested, and code-reviewed without execution.
- Production code can swap the `sleep` injector (e.g. asyncio `asyncio.sleep`).
- Two-entry API surface (`compute_wait` + `retry_call`) is easier to learn
  than a decorator DSL with twenty options.
