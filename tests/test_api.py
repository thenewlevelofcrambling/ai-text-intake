from fastapi.testclient import TestClient

from app.analyzers import AnalyzerError
from app.config import get_settings
from app.main import app, get_analyzer


def test_health_reports_available_mode(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["analyzer_mode"] in {"mock", "anthropic"}


def test_analyze_returns_structured_result(client: TestClient) -> None:
    response = client.post(
        "/analyze",
        json={"text": "Не могу войти в личный кабинет после смены пароля."},
    )

    assert response.status_code == 200
    assert response.headers["X-Analysis-Provider"] == "mock"
    assert response.json() == {
        "category": "technical_issue",
        "priority": "high",
        "summary": "Не могу войти в личный кабинет после смены пароля.",
        "needs_human": True,
        "confidence": 0.88,
    }


def test_analyze_rejects_blank_text(client: TestClient) -> None:
    response = client.post("/analyze", json={"text": "   "})

    assert response.status_code == 422


def test_analyze_rejects_text_that_is_too_short_after_trim(client: TestClient) -> None:
    response = client.post("/analyze", json={"text": "  a"})

    assert response.status_code == 422


def test_anthropic_mode_without_key_is_reported(monkeypatch) -> None:
    monkeypatch.setenv("ANALYZER_MODE", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_analyzer.cache_clear()

    try:
        with TestClient(app) as test_client:
            health_response = test_client.get("/health")
            analyze_response = test_client.post(
                "/analyze", json={"text": "Проверить настройку сервиса"}
            )
    finally:
        get_settings.cache_clear()
        get_analyzer.cache_clear()

    assert health_response.json()["status"] == "degraded"
    assert analyze_response.status_code == 503
    assert analyze_response.json()["detail"]["code"] == "configuration_error"


def test_analyzer_failure_is_structured() -> None:
    class BrokenAnalyzer:
        provider = "anthropic"

        def analyze(self, text: str):
            raise AnalyzerError("Anthropic API request failed")

    app.dependency_overrides[get_analyzer] = BrokenAnalyzer
    try:
        with TestClient(app) as test_client:
            response = test_client.post("/analyze", json={"text": "Проверка ошибки"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "analysis_failed",
            "message": "Anthropic API request failed",
        }
    }
