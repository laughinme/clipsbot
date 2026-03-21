import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api import get_api_routers
from webhooks import get_webhooks
from core.config import Settings, configure_logging, get_settings
from core.error_handling import register_exception_handlers
from core.middlewares import RequestTracingMiddleware
from core.rate_limit import init_rate_limiters
from database.redis import close_redis, init_redis
from database.relational_db import dispose_engine, get_session_factory, wait_for_db
from scheduler import init_scheduler, stop_scheduler
from service.media import get_media_storage_service


logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    enable_rate_limiter: bool = True,
    check_db_on_startup: bool = True,
    enable_scheduler: bool | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = None
        try:
            if check_db_on_startup:
                await wait_for_db()

            redis = init_redis(settings)
            if enable_rate_limiter:
                await init_rate_limiters(app, redis)

            if settings.STORAGE_AUTO_CREATE_BUCKETS:
                storage = get_media_storage_service()
                await asyncio.to_thread(storage.ensure_buckets)

            should_run_scheduler = (
                settings.SCHEDULER_ENABLED if enable_scheduler is None else enable_scheduler
            )
            if should_run_scheduler:
                scheduler = init_scheduler(settings)

            yield
        finally:
            stop_scheduler(scheduler)
            await close_redis()
            await dispose_engine()

    app = FastAPI(
        lifespan=lifespan,
        title="Backend Template",
        debug=settings.DEBUG if settings.DEBUG is not None else settings.APP_STAGE == "dev",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.enable_rate_limit = enable_rate_limiter
    app.add_middleware(RequestTracingMiddleware)
    register_exception_handlers(app, settings)

    app.include_router(get_api_routers())
    app.include_router(get_webhooks())


    # Checks
    @app.get("/api/ping")
    @app.get("/api/health")
    async def liveness():
        return {"status": "operating"}

    @app.get("/api/ready")
    async def readiness():
        checks: dict[str, str] = {}
        try:
            session_factory = get_session_factory(settings)
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            logger.warning("Database readiness check failed: %s", exc)
            checks["database"] = "error"

        try:
            redis = init_redis(settings)
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            logger.warning("Redis readiness check failed: %s", exc)
            checks["redis"] = "error"

        try:
            storage = get_media_storage_service()
            await asyncio.to_thread(storage.check_health)
            checks["storage"] = "ok"
        except Exception as exc:
            logger.warning("Storage readiness check failed: %s", exc)
            checks["storage"] = "error"
        
        if any(value != "ok" for value in checks.values()):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "checks": checks},
            )

        return {"status": "ready", "checks": checks}

    return app


app = create_app()
