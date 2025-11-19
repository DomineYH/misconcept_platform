PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "scenario" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    prompt TEXT NOT NULL,
    student_profile TEXT,
    framework_id INTEGER REFERENCES framework(id),
    created_by INTEGER NOT NULL REFERENCES user(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);
INSERT INTO scenario VALUES(1,'Fraction Addition Misconception','You are a 5th grade student who believes that when adding fractions, you add both numerators and denominators directly (e.g., 1/2 + 1/3 = 2/5). You are working on the problem: What is 1/4 + 1/2?','Grade 5 student, strong in whole number arithmetic but struggles with fraction concepts',1,1,'2025-11-06 11:23:39',1);
COMMIT;
