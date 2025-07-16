CREATE TABLE IF NOT EXISTS mama_bot_configs (
    chat_id BIGINT PRIMARY KEY,
    bot_name VARCHAR(255) NOT NULL,
    child_user_id BIGINT NOT NULL,
    child_first_name VARCHAR(255) NOT NULL,
    gender VARCHAR(16) DEFAULT 'unknown', -- 'male', 'female', 'unknown'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (now() at time zone 'utc')
);

CREATE INDEX IF NOT EXISTS idx_mama_bot_configs_child_user_id ON mama_bot_configs(child_user_id);