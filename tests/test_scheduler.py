import pytest
from unittest.mock import AsyncMock, MagicMock
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo

from tests.test_operator import redis_client, test_config, brain_service_mock
from tests.test_listener import db_manager_mock

from core.scheduler import SchedulerManager
from core.config.parameters import MORNING_ONLINE_DURATION

# ---- Фикстуры

@pytest.fixture
def scheduler() -> AsyncIOScheduler:
    """Создает реальный AsyncIOScheduler для тестов."""
    scheduler_instance = AsyncIOScheduler()
    yield scheduler_instance
    if scheduler_instance.running:
        scheduler_instance.shutdown(wait=False)


@pytest.fixture
def scheduler_manager(
        scheduler: AsyncIOScheduler,
        redis_client,
        db_manager_mock,
        brain_service_mock
)-> SchedulerManager:
    """Создает SchedulerManager c реальным планировщиком и моками зависимостей."""
    return SchedulerManager(scheduler, redis_client, db_manager_mock, brain_service_mock)

@pytest.mark.asyncio
async def test_start_schedulers(
        scheduler_manager: SchedulerManager, db_manager_mock: AsyncMock, mocker, test_config: dict
):
    db_manager_mock.get_all_mama_configs.return_value = [test_config]

    mocker.patch('core.scheduler.random.randint', return_value=15)
    spy = mocker.spy(scheduler_manager.scheduler, 'add_job')

    await scheduler_manager.start()

    expected_job_ids = [
        f"gathering_morning_{test_config['id']}",
        f"online_morning_{test_config['id']}",
        f"gathering_afternoon_{test_config['id']}",
        f"online_afternoon_{test_config['id']}",
        f"gathering_evening_{test_config['id']}",
        f"online_evening_{test_config['id']}",
        f"random_day_{test_config['id']}",
        f"random_night_{test_config['id']}"
    ]

    actual_job_ids = [call.kwargs['id'] for call in spy.call_args_list]
    for job_id in expected_job_ids:
        assert job_id in actual_job_ids

    morning_call = next(
        call for call in spy.call_args_list if call.kwargs['id'] == f"gathering_morning_{test_config['id']}")
    assert morning_call.kwargs['second'] == 15
    assert morning_call.kwargs['args'] == [test_config['id'], 'morning']

@pytest.mark.asyncio
async def test_run_gathering_start_sets_mode(
        scheduler_manager: SchedulerManager,
        redis_client,
        test_config: dict
):
    await scheduler_manager._run_gathering_start(test_config['id'], 'morning')
    mode = await redis_client.get_mode(test_config['id'])
    assert mode == 'GATHERING'
    value = await redis_client.get_string(f"timeofday:{test_config['id']}")
    assert value == 'morning'

@pytest.mark.asyncio
async def test_run_processing_and_online_start_calls_brain_and_sets_jobs(
        scheduler_manager: SchedulerManager,
        redis_client,
        brain_service_mock,
        mocker,
        test_config: dict
):
    spy = mocker.spy(scheduler_manager.scheduler, 'add_job')

    await scheduler_manager._run_processing_and_online_start(
        test_config['id'], 'morning', MORNING_ONLINE_DURATION, ZoneInfo('UTC')
    )

    brain_service_mock.process_gathering_queues.assert_awaited_with(test_config['id'], 'morning')
    mode = await redis_client.get_mode(test_config['id'])
    assert mode == "ONLINE"

    job_ids = [call.kwargs['id'] for call in spy.call_args_list]
    assert any("online_pulse_" in jid for jid in job_ids)
    assert any("online_end_" in jid for jid in job_ids)

@pytest.mark.asyncio
async def test_run_online_end_removes_pulse_and_calls_say_goodbye(
        scheduler_manager: SchedulerManager,
        brain_service_mock,
        mocker,
        test_config: dict
):
    pulse_job_id = f"pulse_job_{test_config['id']}"

    mocker.patch.object(scheduler_manager.scheduler, 'get_job', return_value=MagicMock())
    remove_mock = mocker.patch.object(scheduler_manager.scheduler, 'remove_job')

    await scheduler_manager._run_online_end(test_config['id'], pulse_job_id)

    remove_mock.assert_called_with(pulse_job_id)
    brain_service_mock.say_goodbye_and_switch_to_passive.assert_awaited_with(test_config['id'])

@pytest.mark.asyncio
async def test_random_session_check_success_schedules_jobs(
        scheduler_manager: SchedulerManager,
        redis_client,
        mocker,
        test_config: dict
):
    await redis_client.set_mode(test_config['id'], "PASSIVE")
    mocker.patch('core.scheduler.random.random', return_value=0.0)
    spy = mocker.spy(scheduler_manager.scheduler, 'add_job')

    await scheduler_manager._run_random_session_check(
        test_config['id'], ZoneInfo('UTC'), 100, 10
    )

    assert spy.call_count == 1
    call_kwargs = spy.call_args_list[0].kwargs
    assert call_kwargs['args'][0] == test_config['id']
    assert call_kwargs['args'][1] == "random"
    assert call_kwargs['args'][2] == 10

@pytest.mark.asyncio
async def test_random_session_check_fail_does_nothing(
        scheduler_manager: SchedulerManager,
        redis_client,
        mocker,
        test_config: dict
):
    await redis_client.set_mode(test_config['id'], "PASSIVE")
    mocker.patch('core.scheduler.random.random', return_value=1.0)
    spy = mocker.spy(scheduler_manager.scheduler, 'add_job')

    await scheduler_manager._run_random_session_check(
        test_config['id'], ZoneInfo('UTC'), 100, 10
    )

    spy.assert_not_called()


@pytest.mark.asyncio
async def test_random_session_check_non_passive_does_nothing(
        scheduler_manager: SchedulerManager,
        redis_client,
        mocker,
        test_config: dict
):
    await redis_client.set_mode(test_config['id'], "GATHERING")
    mocker.patch('core.scheduler.random.random', return_value=0.0)
    spy = mocker.spy(scheduler_manager.scheduler, 'add_job')

    await scheduler_manager._run_random_session_check(
        test_config['id'], ZoneInfo('UTC'), 100, 10
    )

    spy.assert_not_called()




