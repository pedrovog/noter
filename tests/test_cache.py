import pytest

from noter.cache import check_duplicate, get_cached, register_usage, save_cache

DB = ":memory:"


@pytest.fixture(autouse=True)
def reset_connections():
    from noter import cache

    cache._connections.clear()
    yield
    cache._connections.clear()


def test_cache_miss_returns_none():
    assert get_cached("https://example.com", db_path=DB) is None


def test_save_and_hit():
    save_cache("https://example.com", "conteúdo", db_path=DB)
    result = get_cached("https://example.com", db_path=DB)
    assert result == "conteúdo"


def test_ttl_expired(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from noter import cache

    save_cache("https://old.com", "velho", db_path=DB)
    future = datetime.now(timezone.utc) + timedelta(days=31)
    monkeypatch.setattr(cache, "_now", lambda: future)
    assert get_cached("https://old.com", ttl_days=30, db_path=DB) is None


def test_duplicate_detection():
    register_usage("https://dup.com", "/vault/nota-a.md", db_path=DB)
    register_usage("https://dup.com", "/vault/nota-b.md", db_path=DB)
    notes = check_duplicate("https://dup.com", db_path=DB)
    assert "/vault/nota-a.md" in notes
    assert "/vault/nota-b.md" in notes


def test_no_duplicate_for_new_url():
    assert check_duplicate("https://novo.com", db_path=DB) == []


def test_save_cache_overwrites_existing():
    save_cache("https://example.com", "first", db_path=DB)
    save_cache("https://example.com", "second", db_path=DB)
    assert get_cached("https://example.com", db_path=DB) == "second"


def test_register_usage_idempotent():
    register_usage("https://dup.com", "/vault/note.md", db_path=DB)
    register_usage("https://dup.com", "/vault/note.md", db_path=DB)
    notes = check_duplicate("https://dup.com", db_path=DB)
    assert notes.count("/vault/note.md") == 1
