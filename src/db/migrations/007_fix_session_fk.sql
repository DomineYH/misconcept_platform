-- Migration 007: Fix session FK to reference scenario
-- Reason: Migration 003 orphaned session.scenario_id FK
-- Date: 2025-11-17
-- Impact: Fixes "no such table: scenario_legacy" error

-- ==============================================
-- Fix session table FK to reference scenario
-- ==============================================

-- SQLite: ALTER TABLE doesn't support modifying FK
-- Must recreate table with correct FK

BEGIN TRANSACTION;

-- 1. Create new session table with correct FK
CREATE TABLE session_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id INTEGER NOT NULL REFERENCES scenario(id),
  teacher_id INTEGER NOT NULL REFERENCES user(id),
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at DATETIME
);

-- 2. Copy all data from old session table
INSERT INTO session_new (
  id, scenario_id, teacher_id, started_at, ended_at
)
SELECT
  id, scenario_id, teacher_id, started_at, ended_at
FROM session;

-- 3. Drop old session table
DROP TABLE session;

-- 4. Rename new table to session
ALTER TABLE session_new RENAME TO session;

-- 5. Recreate indexes
CREATE INDEX IF NOT EXISTS ix_session_teacher_started
  ON session(teacher_id, started_at);
CREATE INDEX IF NOT EXISTS ix_session_ended
  ON session(ended_at);

COMMIT;
