import pytest
from unittest.mock import AsyncMock, MagicMock
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo

from core.scheduler import SchedulerManager
from core.config.parameters import MORNING_ONLINE_DURATION
from core.config.botmode import BotMode

# ---- Фикстуры

@pytest.fixture
def scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler()
    yield sched
    if sched.running:
        sched.shutdown(wait=False)


@pytest.fixture
def scheduler_manager(scheduler):
    redis_mock = AsyncMock()
    db_mock = AsyncMock()
    brain_mock = AsyncMock()
    return SchedulerManager(scheduler, redis_mock, db_mock, brain_mock)


@pytest.mark.asyncio
async def test_start_schedulers_creates_all_jobs(scheduler_manager, mocker):
    test_config = {"id": 1, "timezone": "UTC"}
    scheduler_manager.db.get_all_mama_configs.return_value = [test_config]
    spy = mocker.spy(scheduler_manager.scheduler, "add_job")
    mocker.patch("core.scheduler.random.randint", return_value=30)

    await scheduler_manager.start()

    expected_job_ids = [
        f"gathering_morning_1", f"online_morning_1",
        f"gathering_afternoon_1", f"online_afternoon_1",
        f"gathering_evening_1", f"online_evening_1",
        f"random_day_1", f"random_night_1"
    ]
    actual_job_ids = [call.kwargs["id"] for call in spy.call_args_list]
    for job_id in expected_job_ids:
        assert job_id in actual_job_ids


@pytest.mark.asyncio
async def test_run_gathering_start_sets_redis_mode(scheduler_manager):
    scheduler_manager.redis.set_mode = AsyncMock()
    scheduler_manager.redis.set_string = AsyncMock()

    await scheduler_manager._run_gathering_start(1, "morning")

    scheduler_manager.redis.set_mode.assert_awaited_with(1, BotMode.GATHERING.value)
    scheduler_manager.redis.set_string.assert_awaited_with("timeofday:1", "morning")


@pytest.mark.asyncio
async def test_run_processing_and_online_start_sets_mode_and_jobs(scheduler_manager, mocker):
    scheduler_manager.brain.start_online_interactions = AsyncMock()
    scheduler_manager.redis.set_mode = AsyncMock()
    spy = mocker.spy(scheduler_manager.scheduler, "add_job")

    await scheduler_manager._run_processing_and_online_start(1, "morning", MORNING_ONLINE_DURATION, ZoneInfo("UTC"))

    scheduler_manager.brain.start_online_interactions.assert_awaited_with(1, "morning")
    scheduler_manager.redis.set_mode.assert_awaited_with(1, BotMode.ONLINE.value)
    job_ids = [call.kwargs["id"] for call in spy.call_args_list]
    assert any("online_pulse_" in jid for jid in job_ids)
    assert any("online_end_" in jid for jid in job_ids)


@pytest.mark.asyncio
async def test_run_online_end_removes_pulse_and_calls_brain(scheduler_manager, mocker):
    pulse_job_id = "pulse_job_1"
    scheduler_manager.scheduler.get_job = MagicMock(return_value=MagicMock())
    remove_mock = mocker.patch.object(scheduler_manager.scheduler, "remove_job")
    scheduler_manager.brain.say_goodbye_and_switch_to_passive = AsyncMock()

    await scheduler_manager._run_online_end(1, pulse_job_id)

    remove_mock.assert_called_with(pulse_job_id)
    scheduler_manager.brain.say_goodbye_and_switch_to_passive.assert_awaited_with(1)


@pytest.mark.asyncio
async def test_run_random_session_check_executes_when_passive(scheduler_manager, mocker):
    scheduler_manager.redis.get_mode = AsyncMock(return_value=BotMode.PASSIVE.value)
    scheduler_manager._run_gathering_start = AsyncMock()
    spy = mocker.spy(scheduler_manager.scheduler, "add_job")
    mocker.patch("core.scheduler.random.random", return_value=0.0)  # гарантируем запуск

    await scheduler_manager._run_random_session_check(1, ZoneInfo("UTC"), 100, 10)

    scheduler_manager._run_gathering_start.assert_awaited_with(1, "random")
    call_kwargs = spy.call_args_list[0].kwargs
    assert call_kwargs["args"][0] == 1
    assert call_kwargs["args"][1] == "random"


@pytest.mark.asyncio
async def test_run_random_session_check_no_execution_when_not_passive(scheduler_manager, mocker):
    scheduler_manager.redis.get_mode = AsyncMock(return_value=BotMode.GATHERING.value)
    spy = mocker.spy(scheduler_manager.scheduler, "add_job")
    mocker.patch("core.scheduler.random.random", return_value=0.0)

    await scheduler_manager._run_random_session_check(1, ZoneInfo("UTC"), 100, 10)
    spy.assert_not_called()


@pytest.mark.asyncio
async def test_run_random_session_check_no_execution_due_to_chance(scheduler_manager, mocker):
    scheduler_manager.redis.get_mode = AsyncMock(return_value=BotMode.PASSIVE.value)
    spy = mocker.spy(scheduler_manager.scheduler, "add_job")
    mocker.patch("core.scheduler.random.random", return_value=1.0)  # не сработает

    await scheduler_manager._run_random_session_check(1, ZoneInfo("UTC"), 100, 10)
    spy.assert_not_called()
