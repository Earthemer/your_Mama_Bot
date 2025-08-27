-- Хранит базовые настройки и кастомную "личность" для LLM.
CREATE TABLE IF NOT EXISTS mama_configs (
    id                  SERIAL PRIMARY KEY,
    chat_id             BIGINT NOT NULL UNIQUE,
    bot_name            TEXT NOT NULL,
    admin_id            BIGINT NOT NULL,
    child_participant_id INT,
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
    custom_name             TEXT NOT NULL,
    gender                  TEXT NOT NULL,
    relationship_score      INTEGER NOT NULL DEFAULT 50
        CHECK (relationship_score >= 0 AND relationship_score <= 100),
    is_ignored              BOOLEAN NOT NULL DEFAULT false,
    last_interaction_at     TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT (now() at time zone 'utc'),
    updated_at              TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);
-- Таблица 3: Журнал сообщений
CREATE TABLE IF NOT EXISTS message_log (
    id                  SERIAL PRIMARY KEY,
    config_id           INTEGER NOT NULL REFERENCES mama_configs(id) ON DELETE CASCADE,
    participant_id      INTEGER,
    user_id             BIGINT NOT NULL,
    message_text        TEXT,
    message_type        TEXT NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);
-- Таблица 4: Долгосрочная память (Архив)
CREATE TABLE IF NOT EXISTS long_term_memory (
    id                  SERIAL PRIMARY KEY,
    participant_id      INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    memory_summary      TEXT NOT NULL,
    importance_level    INTEGER NOT NULL DEFAULT 1
        CHECK (importance_level >= 1 AND importance_level <= 5),
    created_at          TIMESTAMPTZ DEFAULT (now() at time zone 'utc')
);


-- =================================================================
-- ИНДЕКСЫ И ТРИГГЕРЫ
-- =================================================================


ALTER TABLE mama_configs
ADD CONSTRAINT fk_child_participant_id
FOREIGN KEY (child_participant_id)
REFERENCES participants(id)
ON DELETE SET NULL
DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX IF NOT EXISTS idx_mama_configs_chat_id ON mama_configs(chat_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_participant ON participants(config_id, user_id);
CREATE INDEX IF NOT EXISTS idx_message_log_config_id_time ON message_log(config_id, created_at);

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