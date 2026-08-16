#!/usr/bin/env bash
# retrymap demo: flaky service recovery + deterministic schedules
set -u
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

echo "== recovery run =="
python3 src/retrymap/demo.py
echo
echo "== schedules =="
for p in exponential constant linear; do
    echo "-- $p --"
    python3 -m retrymap "$p" --base 1 --cap 32 --attempts 5 --no-jitter
done
