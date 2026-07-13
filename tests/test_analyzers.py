from types import SimpleNamespace

import pytest

from app.analyzers import AnthropicAnalyzer, MockAnalyzer
from app.config import Settings
from app.models import AnalysisResult, RequestCategory, RequestPriority


@pytest.mark.parametrize(
    ("text", "category", "priority"),
    [
        ("После оплаты деньги списались дважды", RequestCategory.BILLING, RequestPriority.MEDIUM),
        ("Сколько стоит корпоративный тариф?", RequestCategory.SALES, RequestPriority.MEDIUM),
        ("Хочу оставить жалобу на поддержку", RequestCategory.COMPLAINT, RequestPriority.HIGH),
        ("Как изменить язык интерфейса?", RequestCategory.GENERAL, RequestPriority.LOW),
    ],
)
def test_mock_classification(text, category, priority) -> None:
    result = MockAnalyzer().analyze(text)

    assert result.category is category
    assert result.priority is priority


def test_mock_summary_is_bounded() -> None:
    result = MockAnalyzer().analyze("Ошибка " + "очень " * 60)

    assert len(result.summary) <= 180
    assert result.summary.endswith("...")


def test_anthropic_analyzer_uses_structured_output() -> None:
    expected = AnalysisResult(
        category=RequestCategory.TECHNICAL_ISSUE,
        priority=RequestPriority.HIGH,
        summary="Клиент не может войти в личный кабинет.",
        needs_human=True,
        confidence=0.96,
    )

    class FakeMessages:
        def parse(self, **kwargs):
            assert kwargs["model"] == "claude-haiku-4-5-20251001"
            assert kwargs["output_format"] is AnalysisResult
            return SimpleNamespace(
                stop_reason="end_turn",
                parsed_output=expected,
            )

    fake_client = SimpleNamespace(messages=FakeMessages())
    settings = Settings(
        analyzer_mode="anthropic",
        anthropic_api_key="test-key",
        anthropic_model="claude-haiku-4-5-20251001",
        anthropic_timeout_seconds=20,
    )

    result = AnthropicAnalyzer(settings, client=fake_client).analyze(
        "Не могу войти в личный кабинет."
    )

    assert result == expected
