import pytest
import pytest_asyncio
import os.path
import asyncpg
import asyncio

from typing import AsyncGenerator
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager
from asyncpg import InvalidSQLStatementNameError
from asyncio import TimeoutError

from core.config.parameters import TEST_DATABASE_URL, TEST_TABLES, fake
from core.database import AsyncDatabaseManager
from core.postgres_pool import PostgresPool
from core.exceptions import DatabaseConnectionError, DatabaseQueryError, UnexpectedError, PoolConnectionError


@pytest.fixture(scope='session')
def db_dsn_test() -> str:
    return TEST_DATABASE_URL


@pytest_asyncio.fixture(scope='function')
async def pool_connection(db_dsn_test: str) -> AsyncGenerator[PostgresPool, None]:
    pool_test = PostgresPool(dsn=db_dsn_test)
    await pool_test.create_pool()
    yield pool_test
    if pool_test.is_connected:
        await pool_test.disconnect()


@pytest_asyncio.fixture(scope='function', autouse=True)
async def db_schema_setup(pool_connection: PostgresPool):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_file_path = os.path.join(project_root, 'schema.sql')
    if not os.path.exists(schema_file_path):
        pytest.fail(f"Файл schema.sql не найден: {schema_file_path}")

    with open(schema_file_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    async def drop_all(connection):
        for table in TEST_TABLES:
            await connection.execute(f'DROP TABLE IF EXISTS {table} CASCADE;')

    try:
        async with pool_connection.acquire() as conn:
            await drop_all(conn)
            await conn.execute(schema_sql)
    except Exception as e:
        pytest.fail(f"Ошибка настройки схемы БД (setup): {e}")

    yield

    try:
        async with pool_connection.acquire() as conn:
            await drop_all(conn)
    except Exception as e:
        print(f"Ошибка очистки схемы БД (teardown): {e}")


@pytest_asyncio.fixture(scope='function')
async def db_manager(pool_connection: PostgresPool):
    manager = AsyncDatabaseManager(pool=pool_connection)
    return manager


@pytest_asyncio.fixture(scope='function')
async def bot_data():
    return {
        'chat_id': fake.random_number(digits=9),
        'bot_name': fake.name(),
        'admin_id': fake.random_number(digits=9),
        'timezone': fake.timezone(),
    }


@pytest_asyncio.fixture(scope='function')
async def participant_data():
    return {
        'config_id': fake.random_number(digits=9),
        'custom_name': fake.name(),
        'user_id': fake.random_number(digits=9),
        'timezone': fake.timezone(),
        'gender': 'male'
    }


# --- Тесты ошибки в _execute
@pytest.mark.asyncio
async def test_execute_pool_raises_database_connection_error(pool_connection: PostgresPool,
                                                             db_manager: AsyncDatabaseManager):
    @asynccontextmanager
    async def fake_acquire(*args, **kwargs):
        raise PoolConnectionError("Пул не инициализирован")
        yield

    original_acquire = pool_connection.acquire
    try:
        pool_connection.acquire = fake_acquire
        db_manager.pool = pool_connection

        with pytest.raises(DatabaseConnectionError, match="Пул не инициализирован"):
            await db_manager._execute("SELECT 1", params=(), mode="fetch_val")
    finally:
        pool_connection.acquire = original_acquire


@pytest.mark.asyncio
async def test_execute_raises_query_error_on_postgres_error(db_manager: AsyncDatabaseManager, mocker):
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.side_effect = InvalidSQLStatementNameError("Тестовая ошибка Postgres")
    mocker.patch.object(db_manager._pool, 'acquire', return_value=mock_acquire)

    with pytest.raises(DatabaseQueryError, match="Ошибка запроса к базе данных"):
        await db_manager._execute("SELECT 1")


@pytest.mark.asyncio
async def test_execute_raises_query_error_on_timeout(db_manager: AsyncDatabaseManager, mocker):
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.side_effect = TimeoutError("Тестовый таймаут")
    mocker.patch.object(db_manager._pool, 'acquire', return_value=mock_acquire)

    with pytest.raises(DatabaseQueryError, match="Операция с базой данных завершилась по таймауту."):
        await db_manager._execute("SELECT 1")


@pytest.mark.asyncio
async def test_execute_raises_unexpected_error(db_manager: AsyncDatabaseManager, mocker):
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.side_effect = Exception("Что-то совсем непредвиденное")
    mocker.patch.object(db_manager._pool, 'acquire', return_value=mock_acquire)

    with pytest.raises(UnexpectedError, match="Не предвидимая ошибка"):
        await db_manager._execute("SELECT 1")


# --- Тесты для методов AsyncDatabaseManager
@pytest.mark.asyncio
async def test_upsert_and_get_mama_config(db_manager: AsyncDatabaseManager, bot_data: dict):
    config_id = await db_manager.upsert_mama_config(
        chat_id=bot_data['chat_id'],
        bot_name=bot_data['bot_name'],
        admin_id=bot_data['admin_id'],
        timezone=bot_data['timezone'],
        personality_prompt=None
    )
    retrieved_config = await db_manager.get_mama_config(bot_data['chat_id'])

    assert config_id is not None
    assert isinstance(config_id, int)
    assert retrieved_config is not None
    assert retrieved_config['chat_id'] == bot_data['chat_id']
    assert retrieved_config['bot_name'] == bot_data['bot_name']
    assert retrieved_config['admin_id'] == bot_data['admin_id']
    assert retrieved_config['timezone'] == bot_data['timezone']


@pytest.mark.asyncio
async def test_get_all_mama_config(db_manager: AsyncDatabaseManager, bot_data: dict):
    chat_id = fake.random_number(digits=9)
    chat_id_1 = fake.random_number(digits=9)

    await db_manager.upsert_mama_config(
        chat_id=chat_id,
        bot_name=bot_data['bot_name'],
        admin_id=bot_data['admin_id'],
        timezone=bot_data['timezone'],
        personality_prompt=None
    )

    await db_manager.upsert_mama_config(
        chat_id=chat_id_1,
        bot_name=bot_data['bot_name'],
        admin_id=bot_data['admin_id'],
        timezone=bot_data['timezone'],
        personality_prompt=None
    )

    retrieved_config = await db_manager.get_all_mama_configs()
    chat_ids = [cfg["chat_id"] for cfg in retrieved_config]

    assert chat_id in chat_ids
    assert chat_id_1 in chat_ids


@pytest.mark.asyncio
async def test_delete_mama_config(db_manager: AsyncDatabaseManager, bot_data: dict):
    await db_manager.upsert_mama_config(
        chat_id=bot_data['chat_id'],
        bot_name=bot_data['bot_name'],
        admin_id=bot_data['admin_id'],
        timezone=bot_data['timezone'],
        personality_prompt=None
    )

    configs = await db_manager.get_all_mama_configs()
    assert any(cfg["chat_id"] == bot_data['chat_id'] for cfg in configs)

    deleted_count = await db_manager.delete_mama_config(bot_data['chat_id'])
    assert deleted_count == 1

    configs_after = await db_manager.get_all_mama_configs()
    assert all(cfg["chat_id"] != bot_data['chat_id'] for cfg in configs_after)


@pytest.mark.asyncio
async def test_add_and_get_participant_and_set_child_and_get_child(db_manager: AsyncDatabaseManager, bot_data: dict,
                                                                   participant_data: dict):
    config_id = await db_manager.upsert_mama_config(
        chat_id=bot_data['chat_id'],
        bot_name=bot_data['bot_name'],
        admin_id=bot_data['admin_id'],
        timezone=bot_data['timezone'],
        personality_prompt=None
    )
    participant_dict = await db_manager.add_participant(
        config_id=config_id,
        user_id=participant_data['user_id'],
        custom_name=participant_data['custom_name'],
        gender=participant_data['gender']
    )
    await db_manager.set_child(participant_dict['id'], config_id)
    await db_manager.get_mama_config(bot_data['chat_id'])
    child_dict = await db_manager.get_child(config_id)
    retrieved_data_participant = await db_manager.get_participant(config_id, participant_data['user_id'])

    assert retrieved_data_participant is not None
    assert isinstance(retrieved_data_participant, dict)
    assert isinstance(retrieved_data_participant['id'], int)
    assert retrieved_data_participant['custom_name'] == participant_data['custom_name']
    assert retrieved_data_participant['gender'] == participant_data['gender']
    assert isinstance(retrieved_data_participant['relationship_score'], int)
    assert isinstance(retrieved_data_participant['is_ignored'], bool)
    assert retrieved_data_participant['last_interaction_at'] is None
    assert isinstance(child_dict, dict)
    assert isinstance(child_dict['id'], int)
    assert child_dict['custom_name'] == participant_data['custom_name']


@pytest.mark.asyncio
async def test_update_relationship_scope(db_manager: AsyncDatabaseManager, bot_data: dict,
                                         participant_data: dict):
    config_id = await db_manager.upsert_mama_config(
        chat_id=bot_data['chat_id'],
        bot_name=bot_data['bot_name'],
        admin_id=bot_data['admin_id'],
        timezone=bot_data['timezone'],
        personality_prompt=None
    )

    participant_dict = await db_manager.add_participant(
        config_id=config_id,
        user_id=participant_data['user_id'],
        custom_name=participant_data['custom_name'],
        gender=participant_data['gender']
    )

    participant_id = participant_dict['id']

    original_participant = await db_manager.get_participant(config_id, participant_data['user_id'])
    original_score = original_participant['relationship_score']

    await db_manager.update_relationship_scope(participant_id, 10)

    updated_participant = await db_manager.get_participant(config_id, participant_data['user_id'])

    assert updated_participant['relationship_score'] == original_score + 10


