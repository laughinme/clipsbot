from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from .redis_client import close_redis, get_redis, init_redis
from .cache_interface import CacheRepo


def get_cache_repo(redis: Annotated[Redis, Depends(get_redis)]) -> CacheRepo:
    return CacheRepo(redis)
