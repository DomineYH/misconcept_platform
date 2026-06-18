-- Migration 023: Add app_setting table (Issue #55)
-- Global key/value store for application settings.
-- Row absence for a given key means "use the default".

CREATE TABLE IF NOT EXISTS app_setting (
  key VARCHAR(100) PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
