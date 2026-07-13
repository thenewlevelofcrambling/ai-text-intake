import re
from typing import Protocol

import anthropic
from anthropic import Anthropic

from app.config import Settings
from app.models import AnalysisResult, RequestCategory, RequestPriority


SYSTEM_PROMPT = """You classify incoming customer requests for business routing.

Choose exactly one category:
- technical_issue: errors, access problems, broken functionality
- billing: invoices, charges, refunds, payment questions
- sales: pricing, plans, purchase intent, demos
- complaint: dissatisfaction, service complaints, escalation requests
- general: anything else

Set priority to high for blocked access, broken critical functionality, strong
complaints, or time-sensitive loss. Use medium for billing and purchase intent.
Use low for general informational requests.

Write a factual one-sentence summary in the same language as the request.
Set needs_human=true for high priority, complaints, refunds, or ambiguous cases.
Do not invent names, amounts, dates, or circumstances absent from the request.
"""


class AnalyzerError(RuntimeError):
    """Raised when the selected analyzer cannot produce a valid result."""


class TextAnalyzer(Protocol):
    provider: str

    def analyze(self, text: str) -> AnalysisResult: ...


class MockAnalyzer:
    provider = "mock"

    _category_keywords = {
        RequestCategory.TECHNICAL_ISSUE: (
            "ошиб",
            "не работает",
            "не могу войти",
            "доступ",
            "парол",
            "login",
            "error",
            "broken",
        ),
        RequestCategory.BILLING: (
            "оплат",
            "счет",
            "счёт",
            "возврат",
            "списал",
            "payment",
            "invoice",
            "refund",
        ),
        RequestCategory.SALES: (
            "купить",
            "цена",
            "стоимость",
            "тариф",
            "демо",
            "buy",
            "price",
            "plan",
        ),
        RequestCategory.COMPLAINT: (
            "жалоб",
            "недовол",
            "ужасн",
            "претенз",
            "complaint",
            "unhappy",
        ),
    }

    def analyze(self, text: str) -> AnalysisResult:
        normalized = text.lower()
        category = RequestCategory.GENERAL
        confidence = 0.55

        for candidate, keywords in self._category_keywords.items():
            if any(keyword in normalized for keyword in keywords):
                category = candidate
                confidence = 0.88
                break

        if category in {
            RequestCategory.TECHNICAL_ISSUE,
            RequestCategory.COMPLAINT,
        }:
            priority = RequestPriority.HIGH
        elif category in {RequestCategory.BILLING, RequestCategory.SALES}:
            priority = RequestPriority.MEDIUM
        else:
            priority = RequestPriority.LOW

        needs_human = category in {
            RequestCategory.COMPLAINT,
            RequestCategory.BILLING,
        } or priority is RequestPriority.HIGH

        return AnalysisResult(
            category=category,
            priority=priority,
            summary=self._summarize(text),
            needs_human=needs_human,
            confidence=confidence,
        )

    @staticmethod
    def _summarize(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)[0]
        if len(first_sentence) <= 180:
            return first_sentence
        return first_sentence[:177].rstrip() + "..."


class AnthropicAnalyzer:
    provider = "anthropic"

    def __init__(
        self,
        settings: Settings,
        client: Anthropic | None = None,
    ) -> None:
        if not settings.anthropic_api_key:
            raise AnalyzerError("ANTHROPIC_API_KEY is required in anthropic mode")

        self._settings = settings
        self._client = client or Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.anthropic_timeout_seconds,
            max_retries=1,
        )

    def analyze(self, text: str) -> AnalysisResult:
        try:
            response = self._client.messages.parse(
                model=self._settings.anthropic_model,
                max_tokens=350,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
                output_format=AnalysisResult,
            )
        except anthropic.APIError as exc:
            raise AnalyzerError("Anthropic API request failed") from exc
        except (ValueError, TypeError) as exc:
            raise AnalyzerError("Anthropic returned an invalid structured response") from exc

        if response.stop_reason in {"refusal", "max_tokens"}:
            raise AnalyzerError(f"Anthropic stopped without a result: {response.stop_reason}")
        if response.parsed_output is None:
            raise AnalyzerError("Anthropic returned no structured output")

        return AnalysisResult.model_validate(response.parsed_output)


def build_analyzer(settings: Settings) -> TextAnalyzer:
    if settings.resolved_mode == "mock":
        return MockAnalyzer()
    return AnthropicAnalyzer(settings)
