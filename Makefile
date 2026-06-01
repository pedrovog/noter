.PHONY: install test lint fix planner search

install:
	uv sync

test:
	uv run pytest -v

lint:
	uv run ruff check src/ tests/

fix:
	uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/

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
