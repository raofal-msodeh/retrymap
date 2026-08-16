"""Allow `python3 -m retrymap` to run the CLI."""

from retrymap.cli import main

raise SystemExit(main())
