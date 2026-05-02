"""
Async PostgreSQL connection pool for all tool functions.
Uses asyncpg. Singleton pool created at FastAPI startup.
"""

from typing import Optional

import asyncpg

from core.settings import settings

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Return the global connection pool. Creates it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    """Call on FastAPI shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_conn() -> asyncpg.Connection:
    """Context-manager helper for single queries."""
    pool = await get_pool()
    return pool.acquire()
