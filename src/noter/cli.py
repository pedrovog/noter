import logging
import os
import re
from pathlib import Path

import typer
from dotenv import load_dotenv

from noter import orchestrator

load_dotenv()

app = typer.Typer()

_URL_RE = re.compile(r"^https?://")


def _validate_urls(urls: list[str]) -> list[str]:
    bad = [u for u in urls if not _URL_RE.match(u)]
    if bad:
        typer.echo(
            "Invalid URL(s) — must start with http:// or https://:\n  " + "\n  ".join(bad),
            err=True,
        )
        raise typer.Exit(code=1)
    return urls


@app.command()
def research(
    topic: str = typer.Argument(..., help="Topic to research"),
    source: list[str] = typer.Option([], "--source", "-s", help="Additional URL (repeatable)"),
    source_file: str = typer.Option(None, "--source-file", help=".txt file with one URL per line"),
    no_search: bool = typer.Option(False, "--no-search", help="Skip automatic web search"),
    sources: int = typer.Option(5, "--sources", help="Max automatic sources"),
    cache_ttl: int = typer.Option(30, "--cache-ttl", help="Cache TTL in days"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache reads and writes"),
):
    """Research a topic and generate a note in the Obsidian vault."""
    # Validate --sources
    if sources < 1:
        typer.echo("--sources must be >= 1", err=True)
        raise typer.Exit(code=1)

    # Validate VAULT_PATH
    vault_path = os.environ.get("VAULT_PATH", "")
    if not vault_path or not Path(vault_path).is_dir():
        typer.echo(
            f"VAULT_PATH env var must point to an existing directory (got: {vault_path!r})",
            err=True,
        )
        raise typer.Exit(code=1)

    # Collect URLs from --source-file
    file_urls: list[str] = []
    if source_file:
        p = Path(source_file)
        if not p.exists():
            typer.echo(f"--source-file not found: {source_file}", err=True)
            raise typer.Exit(code=1)
        file_urls = [line.strip() for line in p.read_text().splitlines() if line.strip()]

    user_urls = _validate_urls(list(source) + file_urls)

    orchestrator.run(
        topic=topic,
        vault_path=vault_path,
        user_urls=user_urls,
        n_sources=sources,
        cache_ttl=cache_ttl,
        no_cache=no_cache,
        no_search=no_search,
    )


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    app()
