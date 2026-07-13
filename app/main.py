from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Response

from app.analyzers import AnalyzerError, TextAnalyzer, build_analyzer
from app.config import Settings, get_settings
from app.models import AnalysisRequest, AnalysisResult, HealthResult


app = FastAPI(
    title="AI Text Intake Agent",
    description="Classifies and summarizes text requests with Anthropic or local mock mode.",
    version="1.0.0",
)


@lru_cache
def get_analyzer() -> TextAnalyzer:
    try:
        return build_analyzer(get_settings())
    except AnalyzerError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "configuration_error", "message": str(exc)},
        ) from exc


@app.get("/health", response_model=HealthResult)
def health(settings: Settings = Depends(get_settings)) -> HealthResult:
    missing_required_key = (
        settings.resolved_mode == "anthropic" and not settings.anthropic_api_key
    )
    return HealthResult(
        status="degraded" if missing_required_key else "ok",
        analyzer_mode=settings.resolved_mode,
        anthropic_configured=bool(settings.anthropic_api_key),
    )


@app.post("/analyze", response_model=AnalysisResult)
def analyze(
    payload: AnalysisRequest,
    response: Response,
    analyzer: TextAnalyzer = Depends(get_analyzer),
) -> AnalysisResult:
    try:
        result = analyzer.analyze(payload.text)
    except AnalyzerError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "analysis_failed", "message": str(exc)},
        ) from exc

    response.headers["X-Analysis-Provider"] = analyzer.provider
    return result
