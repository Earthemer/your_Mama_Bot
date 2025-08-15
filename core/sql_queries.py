# core/sql_queries.py

# =================================================================
# ЭТАП 1: Запросы для настройки (Setup)
# =================================================================

UPSERT_MAMA_CONFIG = """
INSERT INTO mama_configs (chat_id, bot_name, admin_id, timezone, personality_prompt)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (chat_id) DO UPDATE SET
    bot_name = EXCLUDED.bot_name,
    admin_id = EXCLUDED.admin_id,
    timezone = EXCLUDED.timezone,
    personality_prompt = EXCLUDED.personality_prompt
RETURNING id;
"""

GET_MAMA_CONFIG = """
SELECT id, chat_id, bot_name, admin_id, timezone, personality_prompt
FROM mama_configs
WHERE chat_id = $1;
"""

GET_ALL_MAMA_CONFIGS = """
SELECT id, chat_id, bot_name, admin_id, timezone, personality_prompt 
FROM mama_configs;
"""

DELETE_MAMA_CONFIG = """
DELETE FROM mama_configs WHERE chat_id = $1;
"""

INSERT_PARTICIPANT = """
INSERT INTO participants (config_id, user_id, role, custom_name, gender)
VALUES ($1, $2, $3, $4, $5)
RETURNING id;
"""

# =================================================================
# ЭТАП 2: Запросы для "мозга" и жизненного цикла
# =================================================================

GET_PARTICIPANT_BY_USER_ID = """
SELECT id, role, custom_name, gender, relationship_score, is_ignored
FROM participants
WHERE config_id = $1 AND user_id = $2;
"""

GET_CHILD_PARTICIPANT = """
SELECT id, custom_name FROM participants
WHERE config_id = $1 AND role = 'child'
LIMIT 1;
"""

UPDATE_RELATIONSHIP_SCORE = """
UPDATE participants
SET relationship_score = relationship_score + $1
WHERE id = $2;
"""

SET_IGNORED_STATUS = """
UPDATE participants
SET is_ignored = $1, relationship_score = 0
WHERE id = $2;
"""

INSERT_DAILY_EVENT = """
INSERT INTO daily_events (participant_id, event_type, event_text)
VALUES ($1, $2, $3);
"""

CHECK_DAILY_EVENT = """
SELECT EXISTS (
    SELECT 1 FROM daily_events
    WHERE participant_id = $1 AND event_type = $2 AND created_at >= date_trunc('day', now() at time zone 'utc')
);
"""

COUNT_DAILY_EVENTS_BY_TYPE = """
SELECT COUNT(*) FROM daily_events
WHERE participant_id = $1 AND event_type = $2 AND created_at >= date_trunc('day', now() at time zone 'utc');
"""

GET_DAILY_EVENTS_SUMMARY = """
SELECT p.custom_name, p.role, de.event_type, de.event_text
FROM daily_events de
JOIN participants p ON de.participant_id = p.id
WHERE p.config_id = $1 AND de.created_at >= date_trunc('day', now() at time zone 'utc')
ORDER BY de.created_at;
"""

INSERT_LONG_TERM_MEMORY = """
INSERT INTO long_term_memory (participant_id, memory_summary)
VALUES ($1, $2);
"""

GET_LONG_TERM_MEMORY = """
SELECT memory_summary FROM long_term_memory
WHERE participant_id = $1
ORDER BY created_at DESC
LIMIT $2;
"""

DELETE_ALL_DAILY_EVENTS = """
DELETE FROM daily_events;
"""

UPDATE_PERSONALITY_PROMPT = "UPDATE mama_configs SET personality_prompt = $1 WHERE id = $2;"