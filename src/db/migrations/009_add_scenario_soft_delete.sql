-- Migration 009: Add soft delete support to scenario table
-- Date: 2025-11-19
-- Purpose: Implement soft delete pattern for scenarios
-- Adds: deleted_at TIMESTAMP column and index
-- Note: Modified to use ALTER TABLE for SQLite compatibility with existing Foreign Keys

BEGIN TRANSACTION;

-- Add the column directly. SQLite supports ADD COLUMN for nullable columns.
ALTER TABLE scenario ADD COLUMN deleted_at TIMESTAMP NULL;

-- Create index for soft delete queries
CREATE INDEX IF NOT EXISTS idx_scenario_deleted ON scenario(deleted_at);

COMMIT;
