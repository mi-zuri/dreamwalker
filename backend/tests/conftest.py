import pytest
from fastapi.testclient import TestClient

from app.settings import settings
from app.storage import get_store
from app.storage.assets import reset_assets


@pytest.fixture(autouse=True)
def fresh_store():
    """Each test gets its own in-process store and no faked loading delays."""
    settings.llm_mode = "mock"
    settings.auth_mode = "dev"
    settings.storage_mode = "memory"
    settings.mock_stage_scale = 0.0
    # No test may reach the network. Ingest is off by default here; the tests
    # that do want a refresh turn it back on and drive it through recorded
    # fixtures with `respx`.
    settings.news_ingest_enabled = False
    settings.pool_min_playable = 0
    get_store.cache_clear()
    reset_assets()
    yield
    get_store.cache_clear()
    reset_assets()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
