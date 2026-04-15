from __future__ import annotations

from collections.abc import AsyncIterator
from threading import RLock
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.config.settings import get_settings

settings = get_settings()

_engine_lock = RLock()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    kwargs: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
    }
    if settings.database_url.startswith("postgresql+asyncpg://"):
        # Avoid stale idle SSL connections on long-lived local/dev processes.
        kwargs.update(
            {
                "pool_recycle": max(60, settings.database_pool_recycle_seconds),
                "pool_use_lifo": True,
                "connect_args": {
                    "command_timeout": max(5, settings.database_command_timeout_seconds),
                },
            }
        )
    return create_async_engine(settings.database_url, **kwargs)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = _build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        with _engine_lock:
            if _session_factory is None:
                _session_factory = async_sessionmaker(
                    bind=get_engine(),
                    expire_on_commit=False,
                    autoflush=False,
                    autocommit=False,
                    class_=AsyncSession,
                )
    return _session_factory


async def initialize_database_engine() -> None:
    # Warm initialization in current process/loop.
    get_session_factory()


async def dispose_database_engine() -> None:
    global _engine, _session_factory
    engine = _engine
    _engine = None
    _session_factory = None
    if engine is not None:
        await engine.dispose()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


class _EngineProxy:
    """Compatibility proxy for legacy imports expecting `engine` object."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_engine(), name)

    async def dispose(self) -> None:
        await dispose_database_engine()


engine = _EngineProxy()


def SessionLocal() -> AsyncSession:
    """Compatibility callable for legacy imports expecting SessionLocal()."""
    return get_session_factory()()
