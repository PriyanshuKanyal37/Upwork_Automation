from fastapi import APIRouter

from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability.metrics import metrics_state

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_v1() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@router.get("/metrics")
async def metrics() -> dict[str, int | float]:
    return metrics_state.snapshot()
