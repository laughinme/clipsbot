from redis.asyncio import Redis
from core.config import Settings, get_settings

_redis_client: Redis | None = None


def init_redis(settings: Settings | None = None) -> Redis:
    global _redis_client

    if _redis_client is None:
        settings = settings or get_settings()
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    return _redis_client


def get_redis() -> Redis:
    """Returns shared Redis client."""
    return init_redis()


async def close_redis() -> None:
    global _redis_client

    if _redis_client is not None:
        await _redis_client.aclose()

    _redis_client = None
