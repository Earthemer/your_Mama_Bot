-- =================================================================
-- ФИНАЛЬНАЯ СХЕМА БД (Версия "Революция" - LLM-driven)
-- =================================================================

-- Хранит базовые настройки и кастомную "личность" для LLM.
CREATE TABLE IF NOT EXISTS mama_configs (
    id                  SERIAL PRIMARY KEY,
    chat_id             BIGINT NOT NULL UNIQUE,
    bot_name            TEXT NOT NULL,
    admin_id            BIGINT NOT NULL,
    timezone            TEXT NOT NULL,
    personality_prompt  TEXT,
    created_at          TIMESTAMPTZ DEFAULT (now() at time zone 'utc'),
    updated_at          TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);
-- Таблица 2: Участники "семьи" (Максимально упрощена)
-- Хранит только ДОЛГОСРОЧНОЕ состояние.
CREATE TABLE IF NOT EXISTS participants (
    id                      SERIAL PRIMARY KEY,
    config_id               INTEGER NOT NULL REFERENCES mama_configs(id) ON DELETE CASCADE,
    user_id                 BIGINT NOT NULL,
    role                    TEXT NOT NULL,
    custom_name             TEXT NOT NULL,
    gender                  TEXT NOT NULL,
    relationship_score      INTEGER NOT NULL DEFAULT 50,
    is_ignored              BOOLEAN NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ DEFAULT (now() at time zone 'utc'),
    updated_at              TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);
-- Таблица 3: Журнал дневных событий
-- "Краткосрочная память" мамы. Хранит ВСЕ одноразовые действия за день.
CREATE TABLE IF NOT EXISTS daily_events (
    id             SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    event_type     TEXT NOT NULL, -- 'greeting', 'thank_you', 'wished_good_night', 'breakfast'
    event_date     DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Таблица 4: Готовые ответы ("Рефлексы")
CREATE TABLE IF NOT EXISTS canned_responses (
    id                  SERIAL PRIMARY KEY,
    context_tag         TEXT NOT NULL UNIQUE,
    response_text       TEXT NOT NULL
);


-- Таблица 4: Журнал дневных событий (Остается, важен для сценариев)
CREATE TABLE IF NOT EXISTS daily_events (
    id             SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    event_type     TEXT NOT NULL, -- 'breakfast', 'bowel_movement', 'brushed_teeth'
    event_date     DATE NOT NULL DEFAULT CURRENT_DATE
);


-- =================================================================
-- ИНДЕКСЫ И ТРИГГЕРЫ
-- =================================================================
CREATE INDEX IF NOT EXISTS idx_mama_configs_chat_id ON mama_configs(chat_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_participant ON participants(config_id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_daily_event ON daily_events(participant_id, event_type, event_date);
CREATE INDEX IF NOT EXISTS idx_canned_responses_context_tag ON canned_responses(context_tag);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = (now() at time zone 'utc');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_mama_configs_updated_at
BEFORE UPDATE ON mama_configs
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_participants_updated_at
BEFORE UPDATE ON participants
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();