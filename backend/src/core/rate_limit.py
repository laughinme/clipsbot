from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import cast

from fastapi import FastAPI, Request, Response
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate, RedisBucket
from redis.asyncio import Redis

AUTH_LIMITER_STATE_KEY = "auth_rate_limiter"
REFRESH_LIMITER_STATE_KEY = "refresh_rate_limiter"

AUTH_BUCKET_KEY = "rate-limit:auth"
REFRESH_BUCKET_KEY = "rate-limit:refresh"

_Identifier = Callable[[Request], Awaitable[str]]


async def _init_redis_bucket(
    redis: Redis,
    *,
    bucket_key: str,
    rate: Rate,
) -> RedisBucket:
    maybe_bucket = RedisBucket.init([rate], redis, bucket_key)
    if isawaitable(maybe_bucket):
        return cast(RedisBucket, await maybe_bucket)
    return cast(RedisBucket, maybe_bucket)


async def init_rate_limiters(app: FastAPI, redis: Redis) -> None:
    auth_bucket = await _init_redis_bucket(
        redis,
        bucket_key=AUTH_BUCKET_KEY,
        rate=Rate(10, Duration.MINUTE),
    )
    refresh_bucket = await _init_redis_bucket(
        redis,
        bucket_key=REFRESH_BUCKET_KEY,
        rate=Rate(10, Duration.MINUTE),
    )

    app.state.auth_rate_limiter = Limiter(auth_bucket)
    app.state.refresh_rate_limiter = Limiter(refresh_bucket)


def build_rate_dependency(
    state_key: str,
    *,
    identifier: _Identifier | None = None,
) -> Callable[[Request, Response], Awaitable[None]]:
    async def dependency(request: Request, response: Response) -> None:
        if getattr(request.app.state, "enable_rate_limit", True) is False:
            return

        limiter = getattr(request.app.state, state_key, None)
        if limiter is None:
            raise RuntimeError(
                f"Rate limiter '{state_key}' is not initialized. "
                "Run init_rate_limiters() in app lifespan."
            )

        limiter_dependency = (
            RateLimiter(limiter=limiter, identifier=identifier)
            if identifier
            else RateLimiter(limiter=limiter)
        )
        await limiter_dependency(request, response)

    return dependency
