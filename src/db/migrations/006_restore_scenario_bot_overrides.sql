-- Migration 006: Restore scenario bot override columns
-- Date: 2025-11-17
-- Purpose: Restore columns accidentally removed by Migration 003
-- Background: Migration 003 removed chatbot_config table but
--   inadvertently removed scenario override columns during table rebuild
-- Restores: chat_model, chat_temperature, tutor_enabled,
--   tutor_intervention_threshold

-- ============================================
-- Strategy: Recreate scenario table with all columns
-- ============================================
-- SQLite does not support ALTER TABLE ADD COLUMN with constraints
-- for multiple columns efficiently, so we recreate the table

BEGIN TRANSACTION;

-- 1. Drop existing indexes (will be recreated later)
DROP INDEX IF EXISTS idx_scenario_framework;
DROP INDEX IF EXISTS idx_scenario_active;

-- 2. Rename existing scenario table to temporary name
ALTER TABLE scenario RENAME TO scenario_legacy;

-- 3. Create new scenario table with all required columns
CREATE TABLE scenario (
    id INTEGER PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    prompt TEXT NOT NULL,
    student_profile TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,

    -- Scenario bot override columns (restored)
    chat_model VARCHAR(50) NULL,
    chat_temperature REAL NULL,
    tutor_enabled BOOLEAN NOT NULL DEFAULT 1,
    tutor_intervention_threshold INTEGER NULL,

    -- Foreign keys
    framework_id INTEGER NOT NULL,
    created_by INTEGER,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CHECK (is_active IN (0, 1)),
    CHECK (chat_temperature IS NULL OR (chat_temperature >= 0 AND chat_temperature <= 2)),
    CHECK (tutor_intervention_threshold IS NULL OR (tutor_intervention_threshold BETWEEN 1 AND 10)),
    FOREIGN KEY (framework_id) REFERENCES analysis_framework(id),
    FOREIGN KEY (created_by) REFERENCES user(id)
);

-- 4. Copy data from legacy table
-- New override columns get NULL (use global config) or DEFAULT values
INSERT INTO scenario (
    id,
    title,
    prompt,
    student_profile,
    is_active,
    chat_model,
    chat_temperature,
    tutor_enabled,
    tutor_intervention_threshold,
    framework_id,
    created_by,
    created_at
)
SELECT
    id,
    title,
    prompt,
    student_profile,
    is_active,
    NULL,  -- chat_model: NULL = use global
    NULL,  -- chat_temperature: NULL = use global
    1,     -- tutor_enabled: DEFAULT = enabled
    NULL,  -- tutor_intervention_threshold: NULL = use global
    framework_id,
    created_by,
    created_at
FROM scenario_legacy;

-- 5. Recreate indexes
CREATE INDEX idx_scenario_framework ON scenario(framework_id);
CREATE INDEX idx_scenario_active ON scenario(is_active);

-- 6. Drop legacy table
DROP TABLE scenario_legacy;

COMMIT;

-- ============================================
-- Verification queries (run after migration)
-- ============================================
-- PRAGMA table_info(scenario);
-- SELECT COUNT(*) FROM scenario;
-- SELECT * FROM scenario;

-- ============================================
-- Rollback procedure (if needed)
-- ============================================
-- If migration fails, restore from backup:
-- cp dialogue_sim.db.backup_pre_fix_20251117_190216 dialogue_sim.db

-- ============================================
-- Column descriptions
-- ============================================
-- chat_model: Override StudentBot model (NULL = use global)
-- chat_temperature: Override temperature 0.0-2.0 (NULL = use global)
-- tutor_enabled: Enable/disable TutorBot (1=enabled, 0=disabled)
-- tutor_intervention_threshold: Override interventions per 10 questions
--   (NULL = use global)
-- ============================================
