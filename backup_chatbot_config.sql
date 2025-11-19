PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE chatbot_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_key TEXT NOT NULL UNIQUE,
  config_value TEXT NOT NULL,
  config_type TEXT NOT NULL CHECK(config_type IN
    ('string','float','int','bool')),
  description TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_by INTEGER REFERENCES user(id)
);
INSERT INTO chatbot_config VALUES(1,'student_bot.model','gpt-5-mini','string','StudentBot LLM model','2025-11-06 11:23:39',NULL);
INSERT INTO chatbot_config VALUES(2,'student_bot.temperature','0.7','float','StudentBot response creativity','2025-11-06 11:23:39',NULL);
INSERT INTO chatbot_config VALUES(3,'student_bot.max_tokens','150','int','StudentBot response length limit','2025-11-06 11:23:39',NULL);
INSERT INTO chatbot_config VALUES(4,'tutor_bot.model','gpt-5-mini','string','TutorBot LLM model','2025-11-06 11:23:39',NULL);
INSERT INTO chatbot_config VALUES(5,'tutor_bot.temperature','0.3','float','TutorBot response consistency','2025-11-06 11:23:39',NULL);
INSERT INTO chatbot_config VALUES(6,'tutor_bot.max_tokens','100','int','TutorBot response length limit','2025-11-06 11:23:39',NULL);
INSERT INTO chatbot_config VALUES(7,'tutor_bot.intervention_threshold','3','int','Interventions per 10 questions','2025-11-06 11:23:39',NULL);
COMMIT;
