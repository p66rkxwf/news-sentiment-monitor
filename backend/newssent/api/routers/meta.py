from fastapi import APIRouter, Request

from newssent.api.schemas import HealthResponse, ModelInfoResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    analyzer = getattr(request.app.state, "analyzer", None)
    return HealthResponse(status="ok", model_loaded=analyzer is not None)


@router.get("/api/model", response_model=ModelInfoResponse)
def model_info(request: Request) -> ModelInfoResponse:
    analyzer = getattr(request.app.state, "analyzer", None)
    if analyzer is None:
        return ModelInfoResponse(model_version="mock-0.0.0", is_mock=True)
    meta = analyzer.metadata
    return ModelInfoResponse(
        model_version=analyzer.version,
        trained_at=meta.get("trained_at"),
        test_macro_f1=meta.get("metrics", {}).get("test", {}).get("macro_f1"),
        is_mock=False,
    )
