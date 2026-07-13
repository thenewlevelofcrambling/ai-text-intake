import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    analyzer_mode: str
    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_timeout_seconds: float

    @property
    def resolved_mode(self) -> str:
        if self.analyzer_mode == "auto":
            return "anthropic" if self.anthropic_api_key else "mock"
        return self.analyzer_mode


@lru_cache
def get_settings() -> Settings:
    mode = os.getenv("ANALYZER_MODE", "auto").strip().lower()
    if mode not in {"auto", "anthropic", "mock"}:
        raise ValueError("ANALYZER_MODE must be auto, anthropic, or mock")

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or None
    timeout = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "20"))
    if timeout <= 0:
        raise ValueError("ANTHROPIC_TIMEOUT_SECONDS must be positive")

    return Settings(
        analyzer_mode=mode,
        anthropic_api_key=api_key,
        anthropic_model=os.getenv(
            "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"
        ).strip(),
        anthropic_timeout_seconds=timeout,
    )
