import pytest
from fastapi.testclient import TestClient

from app.settings import settings
from app.storage import get_store


@pytest.fixture(autouse=True)
def fresh_store():
    """Each test gets its own in-process store and no faked loading delays."""
    settings.llm_mode = "mock"
    settings.auth_mode = "dev"
    settings.storage_mode = "memory"
    settings.mock_stage_scale = 0.0
    get_store.cache_clear()
    yield
    get_store.cache_clear()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
