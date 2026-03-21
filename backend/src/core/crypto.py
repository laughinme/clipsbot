import asyncio
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=2,
)

async def hash_password(password: str) -> str:
    return await asyncio.to_thread(pwd_context.hash, password)

async def verify_password(password: str, hashed_password: str) -> bool:
    return await asyncio.to_thread(pwd_context.verify, password, hashed_password)

async def needs_rehash(hashed_password: str) -> bool:
    return await asyncio.to_thread(pwd_context.needs_update, hashed_password)
