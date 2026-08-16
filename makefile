.PHONY: quality test build example redteam install
install:
pip install -e ".[dev]"
quality:
ruff check src tests
ruff format --check src tests
mypy src
test:
python3 -m pytest -q
build:
rm -rf dist build *.egg-info
python3 -m build
example:
PYTHONPATH=src python3 -m retrymap exponential --base 1 --cap 32 --attempts 5 --no-jitter
redteam:
bash scripts/red_team.sh
