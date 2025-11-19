PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE scenario (
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
, chat_model VARCHAR(50) NULL, chat_temperature REAL NULL
  CHECK (chat_temperature IS NULL OR (chat_temperature >= 0 AND chat_temperature <= 2)), tutor_enabled BOOLEAN NOT NULL DEFAULT 1, tutor_intervention_threshold INTEGER NULL
  CHECK (tutor_intervention_threshold IS NULL OR (tutor_intervention_threshold BETWEEN 1 AND 10)));
INSERT INTO scenario VALUES(1,'Fraction Addition Misconception','You are a 5th grade student who believes that when adding fractions, you add both numerators and denominators directly (e.g., 1/2 + 1/3 = 2/5). You are working on the problem: What is 1/4 + 1/2?','Grade 5 student, strong in whole number arithmetic but struggles with fraction concepts',1,1,1,'2025-11-06 11:23:39',NULL,NULL,1,NULL);
COMMIT;
