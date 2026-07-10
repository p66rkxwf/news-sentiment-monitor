from fastapi import APIRouter

from newssent.api.schemas import HealthResponse, ModelInfoResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # Phase 5 起改為回報 registry 載入的真實模型狀態
    return HealthResponse(status="ok", model_loaded=False)


@router.get("/api/model", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    # Phase 4 模型選定後，改由 newssent/ml/registry.py 讀取真實 metadata.json
    return ModelInfoResponse(model_version="mock-0.0.0", is_mock=True)
