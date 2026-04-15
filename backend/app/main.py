from contextlib import asynccontextmanager
import asyncio
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.ai.skills.n8n import example_picker, node_catalog, skill_loader
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.session import dispose_database_engine, initialize_database_engine
from app.infrastructure.errors.handlers import register_exception_handlers
from app.infrastructure.http.middleware import (
    GlobalRateLimitMiddleware,
    IdempotencyMiddleware,
    RequestContextMiddleware,
    RequestTimeoutMiddleware,
)
from app.infrastructure.logging.setup import configure_logging
from app.infrastructure.queue.broker import configure_broker, is_dramatiq_enabled
from app.interfaces.api.router import api_router

configure_logging()
settings = get_settings()
logger = logging.getLogger(__name__)

_worker = None

if sys.platform == "win32":
    # Avoid Windows Proactor SSL edge-cases with asyncpg under long-lived dev
    # sessions and hot-reload churn.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _worker

    await initialize_database_engine()

    logger.info("n8n node catalog loaded: %s nodes", node_catalog.node_count())
    logger.info("n8n workflow examples loaded: %s examples", example_picker.example_count())
    logger.debug("n8n system prompt loaded: %s chars", len(skill_loader.N8N_SYSTEM_PROMPT))

    if is_dramatiq_enabled():
        from dramatiq import Worker, get_broker
        # Import worker modules so @dramatiq.actor decorators register with the broker.
        from app.workers import job_extraction_worker, job_generation_worker  # noqa: F401

        configure_broker()
        _worker = Worker(get_broker(), worker_threads=2)
        _worker.start()
        logger.info("In-process Dramatiq worker started with 2 threads")

    yield

    if _worker is not None:
        logger.info("Stopping in-process Dramatiq worker")
        _worker.stop()
    await dispose_database_engine()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS must be registered first so it wraps all other middleware. FastAPI runs
# middleware in reverse registration order, so registering CORS first ensures
# preflight OPTIONS requests are never rejected by rate limiting or timeouts.
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(GlobalRateLimitMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}
