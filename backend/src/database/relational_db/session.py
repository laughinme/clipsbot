import asyncio
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import(
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)

from core.config import Settings, get_settings
from .unit_of_work import UoW

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine

    if _engine is None:
        settings = settings or get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.SQL_ECHO,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT_SEC,
        )

    return _engine


def get_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    global _session_factory

    if _session_factory is None:
        engine = get_engine(settings)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)

    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()

    _engine = None
    _session_factory = None


async def wait_for_db(timeout: int = 20, retry_interval: int = 2) -> None:
    start_time = datetime.now()
    deadline = start_time + timedelta(seconds=timeout)
    attempt = 0
    session_factory = get_session_factory()

    logger.info("Attempting to connect to database...")

    while datetime.now() < deadline:
        attempt += 1
        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
                logger.info("Successfully connected to database on attempt %d", attempt)
                return
        except SQLAlchemyError as exc:
            remaining = max((deadline - datetime.now()).seconds, 0)
            logger.warning(
                "Database connection attempt %d failed, retrying for %d more seconds. Error: %s",
                attempt,
                remaining,
                str(exc),
            )
            await asyncio.sleep(retry_interval)
        except Exception as exc:
            remaining = max((deadline - datetime.now()).seconds, 0)
            logger.error(
                "Unexpected error during database connection attempt %d: %s. Retrying for %d more seconds.",
                attempt,
                str(exc),
                remaining,
            )
            await asyncio.sleep(retry_interval)

    raise RuntimeError(
        f"Could not establish database connection after {timeout} seconds and {attempt} attempts."
    )


async def get_uow() -> AsyncGenerator[UoW, None]:
    """Yields Unit of Work instead of raw sessions."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        async with UoW(session) as uow:
            yield uow
