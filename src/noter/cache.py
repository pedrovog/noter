import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path.home() / ".pesquisa" / "cache.db"

# Persistent connections keyed by db_path so :memory: stays alive across calls.
_connections: dict[str, sqlite3.Connection] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    key = str(db_path)
    if key not in _connections:
        if key != ":memory:":
            Path(key).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(key, check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_cache (
                url          TEXT PRIMARY KEY,
                content      TEXT NOT NULL,
                scraped_at   TEXT NOT NULL,
                content_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS url_usage (
                url       TEXT NOT NULL,
                note_path TEXT NOT NULL,
                used_at   TEXT NOT NULL,
                UNIQUE(url, note_path)
            )
        """)
        conn.commit()
        _connections[key] = conn
    return _connections[key]


def get_cached(url: str, ttl_days: int = 30, db_path: Path | str = DB_PATH) -> str | None:
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT content, scraped_at FROM scrape_cache WHERE url = ?", (url,)
    ).fetchone()
    if not row:
        return None
    scraped_at = datetime.fromisoformat(row[1])
    if scraped_at.tzinfo is None:
        scraped_at = scraped_at.replace(tzinfo=timezone.utc)
    if _now() - scraped_at > timedelta(days=ttl_days):
        return None
    return row[0]


def save_cache(url: str, content: str, db_path: Path | str = DB_PATH) -> None:
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    conn = _connect(db_path)
    sql = (
        "INSERT OR REPLACE INTO scrape_cache"
        " (url, content, scraped_at, content_hash) VALUES (?, ?, ?, ?)"
    )
    conn.execute(sql, (url, content, _now().isoformat(), content_hash))
    conn.commit()


def register_usage(url: str, note_path: str, db_path: Path | str = DB_PATH) -> None:
    conn = _connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO url_usage (url, note_path, used_at) VALUES (?, ?, ?)",
        (url, note_path, _now().isoformat()),
    )
    conn.commit()


def check_duplicate(url: str, db_path: Path | str = DB_PATH) -> list[str]:
    conn = _connect(db_path)
    rows = conn.execute("SELECT note_path FROM url_usage WHERE url = ?", (url,)).fetchall()
    return [r[0] for r in rows]
