# RetryMap — Architecture

## Design goals

1. **Deterministic by default.** The retry schedule must be computable without
   executing the function, so tests and reviews can verify timing up front.
   `compute_wait(policy, attempt)` is a pure function.
2. **Injectable time.** `retry_call(fn, config, sleep=time.sleep)` lets tests
   skip real sleeping and lets production swap schedulers.
3. **Failures are data.** `MaxAttemptsError.attempts` carries the full
   exception history; `WaitExceededError` signals deadline breaches. Nothing
   is silently swallowed.
4. **Zero runtime dependencies.** Pure Python 3.11+; `random.Random` is
   isolated per call so jitter never mutates global state.

## Modules

| Module | Responsibility |
| --- | --- |
| `models.py` | Dataclasses: `Policy` variants (`Exponential`/`Constant`/`Linear`/`NoRetry`), `RetryConfig`, `RetryRecord`, `RetryStats`, `Experiment`. Validation lives in `__post_init__`. |
| `engine.py` | `compute_wait` (pure scheduling) and `retry_call` (execution loop with `_matches` predicate logic, deadline accounting, `NoRetryPolicy` short-circuit). `retryable` decorator. |
| `errors.py` | `RetryError` base + `MaxAttemptsError`, `WaitExceededError`, `PolicyError`. |
| `cli.py` | Manual tokenizer over argv; dry-runs a policy schedule. No argparse (zero extra dependencies, fast startup). |
| `suppressions.py` | N/A — retrymap has no file scanning, so no suppression model. |

## Key decisions

- **Predicates over exception lists.** `retry_on` and `do_not_retry` accept a
  type or a callable predicate. A predicate that itself raises is treated as
  *no match* (safe failure) so one bad predicate cannot break a production
  retry loop. `do_not_retry` always wins over `retry_on`.
- **`NoRetryPolicy` short-circuits.** Even when `retry_on` matches,
  `NoRetryPolicy` forces a single attempt — matching the explicit intent.
- **Wall-clock deadline.** `total_deadline` is checked *before* sleeping; the
  failing attempt is still recorded so logs show what was abandoned.

## Testing strategy

- 34 unit/CLI tests covering policies, predicates, deadlines, exhaustion
  history, decorator, and CLI parsing.
- `scripts/red_team.sh`: 17 hostile scenarios (invalid parameters, garbage
  argv, broken predicates, deadline breaches, jitter bounds).
- Jitter tests use a seeded `random.Random(1)` for reproducibility.
