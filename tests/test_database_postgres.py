import pytest
import pytest_asyncio
import os.path

from typing import AsyncGenerator
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager
from asyncpg import InvalidSQLStatementNameError
from asyncio import TimeoutError
from datetime import datetime, timedelta, timezone

from core.config.parameters import TEST_DATABASE_URL, TEST_TABLES, fake
from core.database.postgres_client import AsyncPostgresManager
from core.database.postgres_pool import PostgresPool
from core.config.exceptions import DatabaseConnectionError, DatabaseQueryError, UnexpectedError, PoolConnectionError


@pytest.fixture(scope='session')
def db_dsn_test() -> str:
    """Создает DSN для DB один раз за сессию."""
    return TEST_DATABASE_URL


@pytest_asyncio.fixture
async def pool_connection(db_dsn_test: str) -> AsyncGenerator[PostgresPool, None]:
    """Предоставляет генератор с пулом Postgres."""
    pool_test = PostgresPool(dsn=db_dsn_test)
    await pool_test.create_pool()
    yield pool_test
    if pool_test.is_connected:
        await pool_test.disconnect()


@pytest_asyncio.fixture(scope='function', autouse=True)
async def db_schema_setup(pool_connection: PostgresPool):
    """Извлекает и читает schema для разметки DB."""
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


@pytest_asyncio.fixture
async def db_manager(pool_connection: PostgresPool):
    """Предоставляет асинхронный database_client для тестов."""
    manager = AsyncPostgresManager(pool=pool_connection)
    return manager


@pytest_asyncio.fixture
def bot_data():
    """Сборщик данных для бота."""

    def _make_bot_data(**overrides):
        base = {
            'chat_id': fake.random_number(digits=9),
            'bot_name': fake.name(),
            'admin_id': fake.random_number(digits=9),
            'timezone': fake.timezone()
        }
        base.update(overrides)
        return base

    return _make_bot_data


@pytest_asyncio.fixture
def cargo_bot_db(db_manager):
    """Фабрика для бота."""

    async def _insert_bot(bot: dict) -> int:
        return await db_manager.upsert_mama_config(
            chat_id=bot['chat_id'],
            bot_name=bot['bot_name'],
            admin_id=bot['admin_id'],
            timezone=bot['timezone'],
            personality_prompt=None
        )

    return _insert_bot


@pytest_asyncio.fixture
def participant_data():
    """Сборщик данных для участника."""

    def _make_participant_data(**overrides):
        base = {
            'config_id': None,
            'user_id': fake.random_number(digits=9),
            'custom_name': fake.name(),
            'gender': 'male'
        }
        base.update(overrides)
        return base

    return _make_participant_data


@pytest_asyncio.fixture
def cargo_participant_data(db_manager):
    """Фабрика для участника."""

    async def _insert_cargo(data: dict) -> dict:
        return await db_manager.add_participant(
            config_id=data['config_id'],
            user_id=data['user_id'],
            custom_name=data['custom_name'],
            gender=data['gender']
        )

    return _insert_cargo


# --- Тесты ошибки в _execute

async def test_execute_pool_raises_database_connection_error(pool_connection, db_manager):
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


async def test_execute_raises_query_error_on_postgres_error(db_manager, mocker):
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.side_effect = InvalidSQLStatementNameError("Тестовая ошибка Postgres")
    mocker.patch.object(db_manager._pool, 'acquire', return_value=mock_acquire)

    with pytest.raises(DatabaseQueryError, match="Ошибка запроса к базе данных"):
        await db_manager._execute("SELECT 1")


async def test_execute_raises_query_error_on_timeout(db_manager, mocker):
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.side_effect = TimeoutError("Тестовый таймаут")
    mocker.patch.object(db_manager._pool, 'acquire', return_value=mock_acquire)

    with pytest.raises(DatabaseQueryError, match="Операция с базой данных завершилась по таймауту."):
        await db_manager._execute("SELECT 1")


async def test_execute_raises_unexpected_error(db_manager, mocker):
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.side_effect = Exception("Что-то совсем непредвиденное")
    mocker.patch.object(db_manager._pool, 'acquire', return_value=mock_acquire)

    with pytest.raises(UnexpectedError, match="Не предвидимая ошибка"):
        await db_manager._execute("SELECT 1")


# --- Тесты для методов AsyncDatabaseManager

async def test_upsert_and_get_mama_config(db_manager, bot_data, cargo_bot_db):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)
    retrieved_config = await db_manager.get_mama_config(bot['chat_id'])

    assert config_id is not None
    assert isinstance(config_id, int)
    assert retrieved_config is not None
    assert retrieved_config['chat_id'] == bot['chat_id']
    assert retrieved_config['bot_name'] == bot['bot_name']
    assert retrieved_config['admin_id'] == bot['admin_id']
    assert retrieved_config['timezone'] == bot['timezone']


async def test_get_mama_config_by_id(db_manager, bot_data, cargo_bot_db):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)
    retrieved_config = await db_manager.get_mama_config_by_id(config_id)

    assert config_id is not None
    assert isinstance(config_id, int)
    assert retrieved_config is not None
    assert retrieved_config['chat_id'] == bot['chat_id']
    assert retrieved_config['bot_name'] == bot['bot_name']
    assert retrieved_config['admin_id'] == bot['admin_id']
    assert retrieved_config['timezone'] == bot['timezone']


async def test_get_all_mama_config(db_manager, bot_data, cargo_bot_db):
    chat_id = fake.random_number(digits=9)
    chat_id_0 = fake.random_number(digits=9)
    bot = bot_data(chat_id=chat_id)
    await cargo_bot_db(bot)
    bot_0 = bot_data(chat_id=chat_id_0)
    await cargo_bot_db(bot_0)

    retrieved_config = await db_manager.get_all_mama_configs()
    chat_ids = [cfg['chat_id'] for cfg in retrieved_config]

    assert chat_id in chat_ids
    assert chat_id_0 in chat_ids


async def test_delete_mama_config(db_manager, bot_data, cargo_bot_db):
    bot = bot_data()
    await cargo_bot_db(bot)

    configs = await db_manager.get_all_mama_configs()
    assert any(cfg["chat_id"] == bot['chat_id'] for cfg in configs)

    deleted_count = await db_manager.delete_mama_config(bot['chat_id'])
    assert deleted_count == 1

    configs_after = await db_manager.get_all_mama_configs()
    assert all(cfg["chat_id"] != bot['chat_id'] for cfg in configs_after)


async def test_add_and_get_participant_and_set_child_and_get_child(db_manager, bot_data, cargo_bot_db, participant_data,
                                                                   cargo_participant_data):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)
    participant = participant_data(config_id=config_id)
    participant_dict = await cargo_participant_data(participant)
    await db_manager.set_child(participant_dict['id'], config_id)
    await db_manager.get_mama_config(bot['chat_id'])
    child_dict = await db_manager.get_child(config_id)
    retrieved_data_participant = await db_manager.get_participant(config_id, participant['user_id'])

    assert retrieved_data_participant is not None
    assert isinstance(retrieved_data_participant, dict)
    assert isinstance(retrieved_data_participant['id'], int)
    assert retrieved_data_participant['custom_name'] == participant['custom_name']
    assert retrieved_data_participant['gender'] == participant['gender']
    assert isinstance(retrieved_data_participant['relationship_score'], int)
    assert isinstance(retrieved_data_participant['is_ignored'], bool)
    assert retrieved_data_participant['last_interaction_at'] is None
    assert isinstance(child_dict, dict)
    assert isinstance(child_dict['id'], int)
    assert child_dict['custom_name'] == participant['custom_name']


@pytest.mark.asyncio
async def test_get_all_participants_by_config_id(db_manager, bot_data, cargo_bot_db, participant_data,
                                                 cargo_participant_data):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)

    participant1 = participant_data(config_id=config_id)
    participant2 = participant_data(config_id=config_id)

    participant_dict1 = await cargo_participant_data(participant1)
    participant_dict2 = await cargo_participant_data(participant2)

    participants = await db_manager.get_all_participants_by_config_id(config_id)

    assert isinstance(participants, list)
    assert len(participants) >= 2

    ids = [p['id'] for p in participants]
    assert participant_dict1['id'] in ids
    assert participant_dict2['id'] in ids

    for p in participants:
        assert isinstance(p, dict)
        assert isinstance(p['id'], int)
        assert isinstance(p['user_id'], int)
        assert isinstance(p['custom_name'], str)
        assert isinstance(p['gender'], str)
        assert isinstance(p['relationship_score'], int)


async def test_update_relationship_scope(db_manager, bot_data, cargo_bot_db, participant_data,
                                         cargo_participant_data):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)
    participant = participant_data(config_id=config_id)
    participant_dict = await cargo_participant_data(participant)

    participant_id = participant_dict['id']

    original_participant = await db_manager.get_participant(config_id, participant['user_id'])
    original_score = original_participant['relationship_score']

    await db_manager.update_relationship_score(participant_id, 10)

    updated_participant = await db_manager.get_participant(config_id, participant['user_id'])

    assert updated_participant['relationship_score'] == original_score + 10


async def test_update_personality_prompt(db_manager, bot_data, cargo_bot_db):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)
    test_prompt = fake.text(50)
    await db_manager.update_personality_prompt(prompt=test_prompt, config_id=config_id)
    retrieved_bot_data = await db_manager.get_mama_config(bot['chat_id'])

    assert isinstance(retrieved_bot_data['personality_prompt'], str)
    assert retrieved_bot_data['personality_prompt'] == test_prompt


async def test_set_ignore_status(db_manager, bot_data, cargo_bot_db, participant_data, cargo_participant_data):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)
    participant = participant_data(config_id=config_id)
    participant_dict = await cargo_participant_data(participant)

    original_participant = await db_manager.get_participant(config_id, participant['user_id'])
    original_score = original_participant['relationship_score']

    await db_manager.set_ignore_status(participant_dict['id'], True)

    updated_participant = await db_manager.get_participant(config_id, participant['user_id'])
    assert updated_participant['relationship_score'] != original_score
    assert updated_participant['relationship_score'] == 0

async def test_add_and_get_long_term_memory(db_manager, bot_data, cargo_bot_db, participant_data,
                                            cargo_participant_data):
    bot = bot_data()
    config_id = await cargo_bot_db(bot)
    participant = participant_data(config_id=config_id)
    participant_dict = await cargo_participant_data(participant)

    test_memory = "Пользователь любит шоколадное мороженое"
    await db_manager.add_long_term_memory(
        participant_id=participant_dict['id'],
        memory_summary=test_memory,
        importance_level=3
    )

    memories = await db_manager.get_long_term_memory(participant_dict['id'], 5)

    assert memories is not None
    assert test_memory in memories['memory_summary']
