import pytest


@pytest.fixture(autouse=True)
def reset_connections():
    from noter import cache

    cache._connections.clear()
    yield
    cache._connections.clear()
