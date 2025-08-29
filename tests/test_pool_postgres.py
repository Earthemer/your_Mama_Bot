import pytest
import pytest_asyncio
import asyncpg

from typing import AsyncGenerator

from core.config.parameters import TEST_DATABASE_URL
from core.database.postgres_pool import PostgresPool
from core.exceptions import PoolConnectionError


# --- Фикстуры для тестов

@pytest.fixture(scope='session')
def db_dsn_test() -> str:
    return TEST_DATABASE_URL

@pytest_asyncio.fixture(scope='function')
async def clean_pg_pool(db_dsn_test: str) -> PostgresPool:
    return PostgresPool(dsn=db_dsn_test)

@pytest_asyncio.fixture(scope='function')
async def ready_pg_pool(db_dsn_test: str) -> AsyncGenerator[PostgresPool, None]:
    pool_test = PostgresPool(dsn=db_dsn_test)
    await pool_test.create_pool()
    yield pool_test
    if pool_test.is_connected:
        await pool_test.disconnect()


@pytest.mark.asyncio
async def test_initial(clean_pg_pool: PostgresPool):
    assert clean_pg_pool._pool is None
    assert clean_pg_pool.is_connected is False

@pytest.mark.asyncio
async def test_create_pool_success(clean_pg_pool: PostgresPool):
    await clean_pg_pool.create_pool()
    assert clean_pg_pool._pool is not None
    assert isinstance(clean_pg_pool._pool, asyncpg.Pool)
    assert clean_pg_pool.is_connected is True

@pytest.mark.asyncio
async def test_create_pool_error(clean_pg_pool: PostgresPool):
    await clean_pg_pool.create_pool()
    assert clean_pg_pool.is_connected is True
    with pytest.raises(PoolConnectionError, match="Пул уже создан. Необходимо закрыть пул, для создание нового."):
        await clean_pg_pool.create_pool()

@pytest.mark.asyncio
async def test_disconnect_sets_state_correctly(clean_pg_pool: PostgresPool):
    await clean_pg_pool.create_pool()
    assert clean_pg_pool.is_connected is True
    assert clean_pg_pool._pool is not None
    await clean_pg_pool.disconnect()
    assert clean_pg_pool._is_connected is False
    assert clean_pg_pool._pool is None

@pytest.mark.asyncio
async def test_disconnect_when_not_connected(clean_pg_pool: PostgresPool):
    await clean_pg_pool.disconnect()
    assert clean_pg_pool._is_connected is False
    assert clean_pg_pool._pool is None

@pytest.mark.asyncio
async def test_acquire_success(ready_pg_pool: PostgresPool):
    assert ready_pg_pool.is_connected is True
    async with ready_pg_pool.acquire() as conn:
        assert conn is not None
        assert isinstance(conn, asyncpg.Connection)
        result = await conn.fetchval("SELECT 1")
        assert result == 1

@pytest.mark.asyncio
async def test_acquire_when_not_connected(clean_pg_pool: PostgresPool):
    with pytest.raises(PoolConnectionError, match="Пул не инициализирован"):
        async with clean_pg_pool.acquire() as conn: # type: ignore
            pass

@pytest.mark.asyncio
async def test_acquire_after_successful_disconnect(clean_pg_pool: PostgresPool):
    await clean_pg_pool.create_pool()
    await clean_pg_pool.disconnect()
    with pytest.raises(PoolConnectionError, match="Пул не инициализирован"):
        async with clean_pg_pool.acquire() as conn: # type: ignore
            pass