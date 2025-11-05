"""Database schema initialization script."""

import asyncio
from sqlalchemy import text

from src.db.connection import engine, Base


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
  created_by INTEGER REFERENCES user(id),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scenario_active
  ON scenario(is_active);
CREATE INDEX IF NOT EXISTS idx_scenario_framework
  ON scenario(framework_id);

-- Session table
CREATE TABLE IF NOT EXISTS session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id INTEGER NOT NULL REFERENCES scenario(id),
  teacher_id INTEGER NOT NULL REFERENCES user(id),
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_session_teacher_started
  ON session(teacher_id, started_at);
CREATE INDEX IF NOT EXISTS idx_session_ended
  ON session(ended_at);

-- Message table
CREATE TABLE IF NOT EXISTS message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL
    REFERENCES session(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN
    ('student','teacher','tutor')),
  content TEXT NOT NULL,
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
"""


async def init_schema():
    """Execute schema creation SQL."""
    async with engine.begin() as conn:
        # Split SQL by semicolon and execute each statement
        statements = [
            stmt.strip()
            for stmt in SCHEMA_SQL.split(";")
            if stmt.strip()
        ]
        for stmt in statements:
            await conn.execute(text(stmt))
    print("Database schema initialized successfully")


if __name__ == "__main__":
    asyncio.run(init_schema())
