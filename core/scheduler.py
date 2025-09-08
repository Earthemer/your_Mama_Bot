import logging
import random
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.database.redis_client import RedisClient
from core.database.postgres_client import AsyncPostgresManager
from core.brain_service import BrainService
from core.config.parameters import (
    MORNING_GATHERING_HOUR, MORNING_GATHERING_MINUTE, MORNING_ONLINE_DURATION,
    DAY_GATHERING_HOUR, DAY_GATHERING_MINUTE, DAY_ONLINE_DURATION,
    EVENING_GATHERING_HOUR, EVENING_GATHERING_MINUTE, EVENING_ONLINE_DURATION,
    RANDOM_DAY_HOUR, RANDOM_DAY_MINUTE, RANDOM_DAY_CHANCE_PERCENT, RANDOM_ONLINE_DURATION_DAY,
    RANDOM_NIGHT_HOUR, RANDOM_NIGHT_MINUTE, RANDOM_NIGHT_CHANCE_PERCENT, RANDOM_ONLINE_DURATION_NIGHT,
    GATHERING_DURATION_MINUTES
)
from core.logging_config import log_error
from core.exceptions import SchedulerError

logger = logging.getLogger(__name__)


class BotMode(str, Enum):
    """Режимы работы бота."""
    GATHERING = 'GATHERING'
    ONLINE = 'ONLINE'
    PASSIVE = 'PASSIVE'


class SchedulerManager:
    """
    Управляет жизненным циклом бота через APScheduler.
    """

    def __init__(
            self,
            scheduler: AsyncIOScheduler,
            redis_client: RedisClient,
            db_manager: AsyncPostgresManager,
            brain_service: BrainService,
    ):
        self.scheduler = scheduler
        self.redis = redis_client
        self.db = db_manager
        self.brain = brain_service
        logger.info("SchedulerManager инициализирован.")

    async def start(self):
        """Настраивает расписание для всех активных чатов."""
        logger.info("Запуск и настройка расписаний для всех активных чатов...")
        all_configs = await self.db.get_all_mama_configs()

        if not all_configs:
            logger.warning("В базе данных нет активных конфигураций. Расписания не созданы.")
            return

        for config in all_configs:
            self._schedule_daily_routines(config)

        logger.info(f"Успешно настроено расписание для {len(all_configs)} чатов.")

    @log_error
    def _schedule_daily_routines(self, config: dict[str, Any]):
        """Создает повторяющиеся задачи для одного чата."""
        config_id = config['id']

        try:
            timezone = ZoneInfo(config['timezone'])
        except (ZoneInfoNotFoundError, TypeError) as e:
            raise SchedulerError(f"Некорректная таймзона '{config['timezone']}': {e}")

        def schedule_cycle(hour: int, minute: int, duration: int, label: str):
            """Хелпер для планирования одного полного цикла 'сбор + онлайн'."""
            jitter_seconds = random.randint(0, 59)
            gathering_time = datetime.now(timezone).replace(
                hour=hour, minute=minute, second=jitter_seconds, microsecond=0
            )
            online_start_time = gathering_time + timedelta(minutes=GATHERING_DURATION_MINUTES)
            self.scheduler.add_job(
                self._run_gathering_start,
                trigger="cron", hour=gathering_time.hour, minute=gathering_time.minute, second=gathering_time.second,
                timezone=timezone,
                args=[config_id, label], id=f"gathering_{label}_{config_id}", replace_existing=True
            )
            self.scheduler.add_job(
                self._run_processing_and_online_start,
                trigger="cron", hour=online_start_time.hour, minute=online_start_time.minute,
                second=online_start_time.second,
                timezone=timezone,
                args=[config_id, label, duration, timezone], id=f"online_{label}_{config_id}", replace_existing=True
            )

        # --- Плановые циклы
        schedule_cycle(MORNING_GATHERING_HOUR, MORNING_GATHERING_MINUTE, MORNING_ONLINE_DURATION, 'morning')
        schedule_cycle(DAY_GATHERING_HOUR, DAY_GATHERING_MINUTE, DAY_ONLINE_DURATION, 'afternoon')
        schedule_cycle(EVENING_GATHERING_HOUR, EVENING_GATHERING_MINUTE, EVENING_ONLINE_DURATION, 'evening')

        # --- Рандомные "чек-пойнты"
        self.scheduler.add_job(
            self._run_random_session_check,
            trigger="cron", hour=RANDOM_DAY_HOUR, minute=RANDOM_DAY_MINUTE, timezone=timezone,
            args=[config_id, timezone, RANDOM_DAY_CHANCE_PERCENT, RANDOM_ONLINE_DURATION_DAY],
            id=f"random_day_{config_id}", replace_existing=True
        )
        self.scheduler.add_job(
            self._run_random_session_check,
            trigger="cron", hour=RANDOM_NIGHT_HOUR, minute=RANDOM_NIGHT_MINUTE, timezone=timezone,
            args=[config_id, timezone, RANDOM_NIGHT_CHANCE_PERCENT, RANDOM_ONLINE_DURATION_NIGHT],
            id=f"random_night_{config_id}", replace_existing=True
        )

    # ---- АСИНХРОННЫЕ ИСПОЛНИТЕЛИ
    @log_error
    async def _run_gathering_start(self, config_id: int, time_of_day: str):
        """Переводит чат в режим GATHERING и фиксирует контекст времени."""
        logger.debug(f"SCHEDULER: GATHERING '{time_of_day}' для config_id={config_id}")
        await self.redis.set_mode(config_id, BotMode.GATHERING.value)
        await self.redis.set_string(f"timeofday:{config_id}", time_of_day)

    @log_error
    async def _run_processing_and_online_start(self, config_id: int, time_of_day: str, online_duration: int,
                                               timezone: ZoneInfo):
        """Запускает обработку собранных данных и включает ONLINE-режим."""
        logger.debug(f"SCHEDULER: ONLINE '{time_of_day}' для config_id={config_id} на {online_duration} минут")
        try:
            await self.brain.process_gathering_queues(config_id, time_of_day)
        finally:
            await self.redis.set_mode(config_id, BotMode.ONLINE.value)

            pulse_job_id = f"online_pulse_{config_id}_{time_of_day}"
            self.scheduler.add_job(
                self.brain.process_online_batch,
                trigger="interval", seconds=90, args=[config_id],
                id=pulse_job_id, replace_existing=True, max_instances=1
            )

            end_time = datetime.now(timezone) + timedelta(minutes=online_duration)
            self.scheduler.add_job(
                self._run_online_end,
                trigger="date", run_date=end_time,
                args=[config_id, pulse_job_id],
                id=f"online_end_{config_id}_{time_of_day}",
                replace_existing=True
            )

    @log_error
    async def _run_online_end(self, config_id: int, pulse_job_id: str):
        """Завершает ONLINE-режим."""
        logger.info(f"SCHEDULER: Завершение ONLINE для config_id={config_id}")
        if self.scheduler.get_job(pulse_job_id):
            self.scheduler.remove_job(pulse_job_id)
        await self.brain.say_goodbye_and_switch_to_passive(config_id)

    @log_error
    async def _run_random_session_check(
            self, config_id: int, timezone: ZoneInfo, chance_percent: int, online_minutes: int
    ):
        """Проверяет, не занят ли бот, и с вероятностью запускает рандомную сессию."""
        current_mode = await self.redis.get_mode(config_id)
        if current_mode is not None and current_mode != BotMode.PASSIVE.value:
            logger.debug(f"SCHEDULER: Рандом отменён (бот не PASSIVE, сейчас: {current_mode})")
            return

        if random.random() < (chance_percent / 100.0):
            logger.debug(f"SCHEDULER: Рандомная сессия сработала для config_id={config_id}")

            await self._run_gathering_start(config_id, "random")

            processing_time = datetime.now(timezone) + timedelta(minutes=GATHERING_DURATION_MINUTES)
            self.scheduler.add_job(
                self._run_processing_and_online_start,
                trigger="date", run_date=processing_time,
                args=[config_id, "random", online_minutes, timezone],
                id=f"processing_start_random_{config_id}_{int(processing_time.timestamp())}",
                replace_existing=True
            )
        else:
            logger.debug(f"SCHEDULER: Рандом НЕ сработал для config_id={config_id}")
