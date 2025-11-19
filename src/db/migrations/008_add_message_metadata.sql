-- Migration 008: message 테이블에 metadata 컬럼 추가
-- Date: 2025-11-17
-- Reason: ORM 모델과 DB 스키마 불일치 해결
--
-- Issue: src/models/message.py에서 analysis_metadata 속성이
--        metadata 컬럼을 참조하지만, init_schema.py에는 누락됨
--
-- Changes:
--   - message 테이블에 metadata TEXT NULL 컬럼 추가
--   - 오분석 메타데이터 저장용 (JSON 문자열 형식)

BEGIN TRANSACTION;

-- 1. message 테이블에 metadata 컬럼 추가
ALTER TABLE message ADD COLUMN metadata TEXT NULL;

COMMIT;

-- 검증 쿼리
-- PRAGMA table_info(message);
-- 결과에 metadata 컬럼 존재 확인
