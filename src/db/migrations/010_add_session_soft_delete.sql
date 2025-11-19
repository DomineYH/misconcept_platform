-- Migration 010: Add soft delete support to session table
-- Author: Claude (Codex Analysis)
-- Date: 2025-11-19
-- Purpose: Enable soft delete for sessions when scenarios are deleted

-- Add deleted_at column
ALTER TABLE session ADD COLUMN deleted_at TIMESTAMP NULL;

-- Create index for soft delete queries (performance)
CREATE INDEX IF NOT EXISTS idx_session_deleted ON session(deleted_at);

-- Verification: Check schema
-- PRAGMA table_info(session);
