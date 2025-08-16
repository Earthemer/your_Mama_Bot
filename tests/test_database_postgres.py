import os.path
import pytest
import pytest_asyncio

from typing import AsyncGenerator

from core.config.parameters import TEST_DATABASE_URL, TEST_TABLES, fake
from core.database import AsyncDatabaseManager
from core.postgres_pool import PostgresPool



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

@pytest.mark.asyncio
async def test_upsert_and_get_mama_config(db_manager: AsyncDatabaseManager):
    chat_id = fake.random_number(digits=9)
    bot_name = fake.name()
    admin_id = fake.random_number(digits=9)
    timezone = fake.timezone()

    config_id = await db_manager.upsert_mama_config(
        chat_id=chat_id,
        bot_name=bot_name,
        admin_id=admin_id,
        timezone=timezone,
        personality_prompt=None
    )


    retrieved_config = await db_manager.get_mama_config(chat_id)

    assert config_id is not None
    assert isinstance(config_id, int)

    assert retrieved_config is not None
    assert retrieved_config['chat_id'] == chat_id
    assert retrieved_config['bot_name'] == bot_name
    assert retrieved_config['admin_id'] == admin_id
    assert retrieved_config['timezone'] == timezone

@pytest.mark.asyncio
async def test_get_all_mama_config(db_manager: AsyncDatabaseManager):
    real_chat_id_1 = fake.random_number(digits=9)
    real_chat_id_2 = fake.random_number(digits=9)


    await db_manager.upsert_mama_config(
        chat_id=real_chat_id_1,
        bot_name=fake.name(),
        admin_id=fake.random_number(digits=9),
        timezone=fake.timezone(),
        personality_prompt=None
    )
    await db_manager.upsert_mama_config(
        chat_id=real_chat_id_2,
        bot_name=fake.name(),
        admin_id=fake.random_number(digits=9),
        timezone=fake.timezone(),
        personality_prompt=None
    )

    retrieved_config = await db_manager.get_all_mama_configs()
    chat_ids = [cfg["chat_id"] for cfg in retrieved_config]

    assert real_chat_id_1 in chat_ids
    assert real_chat_id_2 in chat_ids

@pytest.mark.asyncio
async def test_delete_mama_config(db_manager: AsyncDatabaseManager):
    chat_id = fake.random_number(digits=9)


    await db_manager.upsert_mama_config(
        chat_id=chat_id,
        bot_name=fake.name(),
        admin_id=fake.random_number(digits=9),
        timezone=fake.timezone(),
        personality_prompt=None
    )


    configs = await db_manager.get_all_mama_configs()
    assert any(cfg["chat_id"] == chat_id for cfg in configs)


    deleted_count = await db_manager.delete_mama_config(chat_id)
    assert deleted_count == 1


    configs_after = await db_manager.get_all_mama_configs()
    assert all(cfg["chat_id"] != chat_id for cfg in configs_after)

@pytest.mark.asyncio
async def test_add_and_get_participant(db_manager: AsyncDatabaseManager):
    chat_id = fake.random_number(digits=9)

    # создаём конфиг
    config_id = await db_manager.upsert_mama_config(
        chat_id=chat_id,
        bot_name=fake.name(),
        admin_id=fake.random_number(digits=9),
        timezone=fake.timezone(),
        personality_prompt=None
    )

    # данные участника
    user_id = fake.random_number(digits=9)
    role = "child"
    custom_name = fake.first_name()
    gender = "female"

    # добавляем участника
    participant_id = await db_manager.add_participant(
        config_id=config_id,
        user_id=user_id,
        role=role,
        custom_name=custom_name,
        gender=gender
    )
    assert participant_id is not None

    # проверяем get_participant
    participant = await db_manager.get_participant(config_id=config_id, user_id=user_id)
    assert participant is not None
    assert participant["id"] == participant_id
    assert participant["role"] == role
    assert participant["custom_name"] == custom_name
    assert participant["gender"] == gender

