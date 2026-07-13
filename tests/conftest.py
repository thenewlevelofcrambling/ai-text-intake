import pytest
from fastapi.testclient import TestClient

from app.analyzers import MockAnalyzer
from app.main import app, get_analyzer


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_analyzer] = MockAnalyzer
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
