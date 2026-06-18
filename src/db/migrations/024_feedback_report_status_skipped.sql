-- Migration 024: Allow 'skipped' status on session_feedback_report (Issue #55)
-- SQLite cannot ALTER a CHECK constraint in place, so rebuild the table.
-- Adds 'skipped' to the status CHECK while preserving all existing rows.

CREATE TABLE session_feedback_report_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL UNIQUE REFERENCES session(id) ON DELETE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  model VARCHAR(64) NOT NULL,
  prompt_hash VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL
    CHECK (status IN ('ok', 'degraded', 'failed', 'skipped')),
  payload_json TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO session_feedback_report_new
  (id, session_id, version, model, prompt_hash, status, payload_json, created_at)
SELECT
  id, session_id, version, model, prompt_hash, status, payload_json, created_at
FROM session_feedback_report;

DROP TABLE session_feedback_report;

ALTER TABLE session_feedback_report_new RENAME TO session_feedback_report;

CREATE INDEX IF NOT EXISTS ix_session_feedback_report_session
  ON session_feedback_report(session_id);

CREATE INDEX IF NOT EXISTS ix_session_feedback_report_status
  ON session_feedback_report(status);
