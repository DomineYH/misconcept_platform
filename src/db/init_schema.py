"""Database schema initialization script."""

import asyncio

from sqlalchemy import text

from src.db.connection import engine

# SQL schema from data-model.md
SCHEMA_SQL = """
-- Enable WAL mode for better concurrent performance
PRAGMA journal_mode=WAL;

-- User table
CREATE TABLE IF NOT EXISTS user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_uid TEXT NOT NULL,
  nickname TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN
    ('teacher','student','admin')) DEFAULT 'teacher',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(student_uid, nickname)
);

-- Analysis Framework table
CREATE TABLE IF NOT EXISTS analysis_framework (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  labels_json TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Scenario table
CREATE TABLE IF NOT EXISTS scenario (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  prompt TEXT NOT NULL,
  student_profile TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
    CHECK(is_active IN (0, 1)),
  framework_id INTEGER NOT NULL
    REFERENCES analysis_framework(id),
  -- Bot configuration overrides (optional)
  chat_model VARCHAR(50) NULL,
  chat_temperature REAL NULL
    CHECK(chat_temperature IS NULL OR
      (chat_temperature >= 0 AND chat_temperature <= 2)),
  tutor_enabled BOOLEAN NOT NULL DEFAULT 1,
  tutor_intervention_threshold INTEGER NULL
    CHECK(tutor_intervention_threshold IS NULL OR
      (tutor_intervention_threshold BETWEEN 1 AND 10)),
  created_by INTEGER REFERENCES user(id),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME NULL
);

CREATE INDEX IF NOT EXISTS idx_scenario_active
  ON scenario(is_active);
CREATE INDEX IF NOT EXISTS idx_scenario_deleted
  ON scenario(deleted_at);
CREATE INDEX IF NOT EXISTS idx_scenario_framework
  ON scenario(framework_id);

-- Session table
CREATE TABLE IF NOT EXISTS session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id INTEGER NOT NULL REFERENCES scenario(id),
  teacher_id INTEGER NOT NULL REFERENCES user(id),
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at DATETIME,
  deleted_at DATETIME NULL
);

CREATE INDEX IF NOT EXISTS idx_session_teacher_started
  ON session(teacher_id, started_at);
CREATE INDEX IF NOT EXISTS idx_session_ended
  ON session(ended_at);
CREATE INDEX IF NOT EXISTS idx_session_deleted
  ON session(deleted_at);

-- Message table
CREATE TABLE IF NOT EXISTS message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL
    REFERENCES session(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN
    ('student','teacher','tutor')),
  content TEXT NOT NULL,
  metadata TEXT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_message_session_created
  ON message(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_message_session_role
  ON message(session_id, role);

-- Question Analysis table
CREATE TABLE IF NOT EXISTS question_analysis (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER NOT NULL UNIQUE
    REFERENCES message(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  confidence REAL CHECK(confidence BETWEEN 0.0 AND 1.0
    OR confidence IS NULL),
  meta_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_question_analysis_label
  ON question_analysis(label);

-- Session Summary table
CREATE TABLE IF NOT EXISTS session_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL UNIQUE
    REFERENCES session(id) ON DELETE CASCADE,
  distribution_json TEXT NOT NULL,
  feedback TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Chatbot Configuration table (Phase 1 - P0)
CREATE TABLE IF NOT EXISTS chatbot_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_key TEXT NOT NULL UNIQUE,
  config_value TEXT NOT NULL,
  config_type TEXT NOT NULL CHECK(config_type IN
    ('string','float','int','bool')),
  description TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_by INTEGER REFERENCES user(id)
);

-- Chatbot Configuration Audit Log (Phase 1 - P0 Security)
CREATE TABLE IF NOT EXISTS chatbot_config_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_key TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT NOT NULL,
  changed_by INTEGER NOT NULL REFERENCES user(id),
  changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ip_address TEXT
);

CREATE INDEX IF NOT EXISTS idx_config_audit_changed_at
  ON chatbot_config_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_config_audit_key
  ON chatbot_config_audit(config_key);

-- API Usage Log table (Task 3.1.1)
CREATE TABLE IF NOT EXISTS api_usage_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES session(id),
  bot_type TEXT NOT NULL CHECK(bot_type IN ('student','tutor')),
  model TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL,
  completion_tokens INTEGER NOT NULL,
  total_tokens INTEGER NOT NULL,
  estimated_cost_usd REAL NOT NULL,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_usage_session
  ON api_usage_log(session_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp
  ON api_usage_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_usage_bot_type
  ON api_usage_log(bot_type);

-- Prompt Template table (Task 3.2.1)
CREATE TABLE IF NOT EXISTS prompt_template (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bot_type TEXT NOT NULL CHECK(bot_type IN ('student', 'tutor')),
  template_name TEXT NOT NULL,
  template_text TEXT NOT NULL
    CHECK(LENGTH(template_text) >= 10 AND LENGTH(template_text) <= 10000),
  version INTEGER NOT NULL DEFAULT 1,
  is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0, 1)),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_by INTEGER REFERENCES user(id)
);

CREATE INDEX IF NOT EXISTS ix_prompt_bot_type
  ON prompt_template(bot_type);
CREATE UNIQUE INDEX IF NOT EXISTS ix_prompt_active
  ON prompt_template(bot_type) WHERE is_active = 1;
CREATE INDEX IF NOT EXISTS ix_prompt_created_at
  ON prompt_template(created_at);
"""


async def init_schema():
    """Execute schema creation SQL."""
    async with engine.begin() as conn:
        # Split SQL by semicolon and execute each statement
        statements = [
            stmt.strip() for stmt in SCHEMA_SQL.split(";") if stmt.strip()
        ]
        for stmt in statements:
            await conn.execute(text(stmt))
    print("Database schema initialized successfully")


if __name__ == "__main__":
    asyncio.run(init_schema())
