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
-- Таблица 2: Участники "семьи"
CREATE TABLE IF NOT EXISTS participants (
    id                      SERIAL PRIMARY KEY,
    config_id               INTEGER NOT NULL REFERENCES mama_configs(id) ON DELETE CASCADE,
    user_id                 BIGINT NOT NULL,
    role                    TEXT NOT NULL,
    custom_name             TEXT NOT NULL,
    gender                  TEXT NOT NULL,
    relationship_score INTEGER NOT NULL DEFAULT 50
        CHECK (relationship_score >= 0 AND relationship_score <= 100),
    is_ignored              BOOLEAN NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ DEFAULT (now() at time zone 'utc'),
    updated_at              TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);
-- Таблица 3: Журнал дневных событий
CREATE TABLE IF NOT EXISTS daily_events (
    id             SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    event_type     TEXT NOT NULL,
    event_text     TEXT,
    created_at     TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);

-- Таблица 3: Долгосрочная память
CREATE TABLE IF NOT EXISTS long_term_memory (
    id             SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    memory_summary TEXT NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);

-- =================================================================
-- ИНДЕКСЫ И ТРИГГЕРЫ
-- =================================================================

CREATE INDEX IF NOT EXISTS idx_mama_configs_chat_id ON mama_configs(chat_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_participant ON participants(config_id, user_id);
CREATE INDEX IF NOT EXISTS idx_daily_events_participant_id_time ON daily_events(participant_id, created_at);

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