import os

import asyncpg
from fastapi import Request


DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/appdb")

_pool = None


async def create_pool():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL)


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_db():
    async with _pool.acquire() as connection:
        yield connection
