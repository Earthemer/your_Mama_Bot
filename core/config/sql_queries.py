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

SET_CHILD = """
UPDATE mama_configs SET child_participant_id = $1 WHERE id = $2;
"""

GET_MAMA_CONFIG = """
SELECT id, chat_id, bot_name, admin_id, child_participant_id, timezone, personality_prompt
FROM mama_configs
WHERE chat_id = $1;
"""

GET_MAMA_CONFIG_BY_ID = """
SELECT id, chat_id, bot_name, admin_id, child_participant_id, timezone, personality_prompt
FROM mama_configs
WHERE id = $1;
"""

GET_ALL_MAMA_CONFIGS = """
SELECT id, chat_id, bot_name, admin_id, child_participant_id, timezone, personality_prompt 
FROM mama_configs;
"""

DELETE_MAMA_CONFIG = """
DELETE FROM mama_configs WHERE chat_id = $1;
"""

INSERT_PARTICIPANT = """
INSERT INTO participants (config_id, user_id, custom_name, gender)
VALUES ($1, $2, $3, $4)
RETURNING id, custom_name;
"""

UPDATE_PERSONALITY_PROMPT = "UPDATE mama_configs SET personality_prompt = $1 WHERE id = $2;"

GET_PARTICIPANT = """
SELECT id, custom_name, gender, relationship_score, is_ignored, last_interaction_at
FROM participants
WHERE config_id = $1 AND user_id = $2;
"""

GET_ALL_PARTICIPANTS_BY_CONFIG_ID = """
SELECT id, user_id, custom_name, gender, relationship_score
FROM participants
WHERE config_id = $1 AND is_ignored = false;
"""

GET_CHILD = """
SELECT p.id, p.custom_name FROM participants p
JOIN mama_configs mc ON p.id = mc.child_participant_id
WHERE mc.id = $1;
"""

UPDATE_RELATIONSHIP_SCORE = """
UPDATE participants
SET 
    relationship_score = GREATEST(0, LEAST(100, relationship_score + $1)),
    last_interaction_at = now() at time zone 'utc'
WHERE id = $2;
"""

SET_IGNORED_STATUS = """
UPDATE participants
SET 
    is_ignored = $1,
    relationship_score = CASE WHEN $1 THEN 0 ELSE relationship_score END
WHERE id = $2;
"""

INSERT_LONG_TERM_MEMORY = """
INSERT INTO long_term_memory (participant_id, memory_summary, importance_level)
VALUES ($1, $2, $3);
"""

GET_LONG_TERM_MEMORY = """
SELECT memory_summary FROM long_term_memory
WHERE participant_id = $1
ORDER BY created_at DESC
LIMIT $2;
"""

