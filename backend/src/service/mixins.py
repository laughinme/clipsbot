from redis.asyncio import Redis

from database.relational_db import UoW


class EnsureUoW:
    """A mixin class ensuring unit of work dependency"""
    def __init__(self, *args, uow: UoW, **kwargs):
        super().__init__(*args, **kwargs)
        self.uow = uow


class EnsureRedis:
    """A mixin class ensuring redis dependency"""
    def __init__(self, *args, redis: Redis, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = redis   


# class EnsureDeps(EnsureUoW, EnsureRedis):
#     """A mixin class ensuring both uow and redis dependencies"""
#     def __init__(self, uow: UoW, redis: Redis):
#         super(EnsureUoW).__init__(uow)
#         super(EnsureRedis).__init__(redis)
