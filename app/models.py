from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class RequestCategory(StrEnum):
    TECHNICAL_ISSUE = "technical_issue"
    BILLING = "billing"
    SALES = "sales"
    COMPLAINT = "complaint"
    GENERAL = "general"


class RequestPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisRequest(BaseModel):
    text: str = Field(
        min_length=3,
        max_length=5_000,
        description="Customer request in free-form text.",
        examples=["Не могу войти в личный кабинет после смены пароля."],
    )

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AnalysisResult(BaseModel):
    category: RequestCategory = Field(description="Best matching request category.")
    priority: RequestPriority = Field(description="Operational handling priority.")
    summary: str = Field(
        min_length=3,
        max_length=240,
        description="A concise summary in the same language as the request.",
    )
    needs_human: bool = Field(
        description="True when a human should review or handle the request."
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Classification confidence from 0 to 1.",
    )


class HealthResult(BaseModel):
    status: str = "ok"
    analyzer_mode: str
    anthropic_configured: bool
