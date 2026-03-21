from fastapi import Depends
from redis.asyncio import Redis

from database.redis import CacheRepo, get_redis
from database.relational_db import UoW, UserInterface, get_uow
from .token_service import TokenService


async def get_token_service(
    redis: Redis = Depends(get_redis),
    uow: UoW = Depends(get_uow),
) -> TokenService:
    cache_repo = CacheRepo(redis)
    user_repo = UserInterface(uow.session)
    return TokenService(cache_repo, user_repo)
