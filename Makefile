# Shortcuts for the four things you do over and over.
#
# A Makefile here is a note to your future self and to whoever clones this next:
# it is the shortest honest answer to "how do I run the tests?".
#
#     make            list the targets
#     make test       run the suite
#     make run        API on :8000
#     make dash       dashboard on :8501 (needs the API running)
#     make docker     both, in containers
#
# Windows note: `make` is not installed by default. Every recipe below is a
# single command you can copy and paste into a terminal instead.

.DEFAULT_GOAL := help
.PHONY: help install test lint format run dash docker clean

help:  ## show this list
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## create the environment from the lock file
	uv sync

test:  ## run the test suite
	uv run pytest -q

lint:  ## check style and common mistakes
	uv run ruff check src tests dashboard

format:  ## fix what can be fixed automatically
	uv run ruff format src tests dashboard
	uv run ruff check --fix src tests dashboard

run:  ## start the API on http://localhost:8000/docs
	uv run uvicorn factoryflow.api:app --reload --port 8000

dash:  ## start the dashboard on http://localhost:8501
	uv run streamlit run dashboard/app.py

docker:  ## build and start both services in containers
	docker compose up --build

clean:  ## remove caches and derived data
	uv run python -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('.pytest_cache','.ruff_cache','htmlcov','data/processed')]"
