# Release audit — retrymap 1.0.0 (2026-08-16)

- ruff check src tests: clean
- ruff format --check src tests: clean
- mypy src: 7 source files, no issues
- pytest: 34 passed
- red-team: 17/17 hostile scenarios rejected or handled safely
- build: wheel + sdist built successfully
- Zero runtime dependencies verified (pyproject lists none)
