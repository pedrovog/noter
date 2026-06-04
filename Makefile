.PHONY: install test lint fix coverage typecheck run run-verbose planner search

install:
	uv sync

test:
	uv run pytest -v

coverage:
	uv run pytest --cov=noter --cov-report=term-missing --cov-report=html

typecheck:
	uv run mypy src/noter/

lint:
	uv run ruff check src/ tests/

fix:
	uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/

# Usage: make run topic="RAG"
run:
	uv run noter "$(topic)" --sources 5

# Usage: make run-verbose topic="RAG"
run-verbose:
	uv run noter "$(topic)" --verbose --sources 2

# Usage: make planner topic="RAG"
planner:
	uv run python -c "\
from dotenv import load_dotenv; load_dotenv(); \
from noter.agents.planner import run; \
import json; \
print(json.dumps(run('$(topic)').model_dump(), indent=2))"

# Usage: make search topic="RAG"
search:
	uv run python -c "\
from dotenv import load_dotenv; load_dotenv(); \
from noter.agents.planner import run as plan; \
from noter.agents.searcher import run as search; \
import json; \
p = plan('$(topic)'); \
results = search(p, [], n_sources=5, cache_ttl=30, no_cache=False, no_search=False); \
print(json.dumps([r.model_dump() for r in results], indent=2))"
