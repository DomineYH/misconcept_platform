PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE chatbot_config_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_key TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT NOT NULL,
  changed_by INTEGER NOT NULL REFERENCES user(id),
  changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ip_address TEXT
);
COMMIT;
