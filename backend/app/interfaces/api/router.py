from fastapi import APIRouter

from app.infrastructure.config.settings import get_settings
from app.interfaces.api.v1.auth import router as auth_router
from app.interfaces.api.v1.connectors import router as connectors_router
from app.interfaces.api.v1.dashboard import router as dashboard_router
from app.interfaces.api.v1.health import router as health_router
from app.interfaces.api.v1.jobs import router as jobs_router
from app.interfaces.api.v1.outputs import router as outputs_router
from app.interfaces.api.v1.profile import router as profile_router
from app.interfaces.api.v1.projects import router as projects_router
from app.interfaces.api.v1.usage import router as usage_router

settings = get_settings()

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(projects_router)
api_router.include_router(jobs_router)
api_router.include_router(outputs_router)
api_router.include_router(connectors_router)
api_router.include_router(usage_router)
api_router.include_router(dashboard_router)
