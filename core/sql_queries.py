UPSERT_MAMA_CONFIG = """
INSERT INTO mama_bot_configs (chat_id, bot_name, child_user_id, child_first_name, gender)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (chat_id) DO UPDATE SET
    bot_name = EXCLUDED.bot_name,
    child_user_id = EXCLUDED.child_user_id,
    child_first_name = EXCLUDED.child_first_name,
    gender = EXCLUDED.gender,
    is_active = TRUE,
    updated_at = (now() at time zone 'utc');
"""

GET_MAMA_CONFIG = """
SELECT chat_id, bot_name, child_user_id, child_first_name, gender, is_active
FROM mama_bot_configs
WHERE chat_id = $1 AND is_active = TRUE;
"""

DELETE_MAMA_CONFIG = """
DELETE FROM mama_bot_configs WHERE chat_id = $1;
"""