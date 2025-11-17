# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **[BREAKING]** 챗봇 설정 관리 방식 변경: 데이터베이스 → .env 파일
  - 관리자 UI (`/admin/chatbot-config/*`) 제거
  - 설정 변경 시 서버 재시작 필요
  - 5개 환경 변수 추가: `STUDENT_TEMPERATURE`, `STUDENT_MAX_TOKENS`, `TUTOR_TEMPERATURE`, `TUTOR_MAX_TOKENS`, `TUTOR_INTERVENTION_THRESHOLD`
- 세션 생명주기 관리를 클라이언트에서 서버로 이동하여 안정성 향상
- HTMX 폴링에 `since` 파라미터 추가로 네트워크 효율 80-90% 개선

### Removed
- 챗봇 설정 관리 API 엔드포인트 (3개)
  - `GET /admin/chatbot-config/settings` - 설정 페이지
  - `GET /admin/chatbot-config/` - 설정 조회
  - `PUT /admin/chatbot-config/` - 설정 업데이트
- `chatbot_config`, `chatbot_config_audit` 데이터베이스 테이블
- `BotConfigCache` 캐싱 시스템 (~120줄)
- 관련 파일 8개 (~1,500줄 총):
  - `src/api/routes/admin_chatbot_config.py`
  - `src/models/chatbot_config.py`
  - `src/services/config_cache.py`
  - `src/templates/admin/chatbot_settings.html`
  - `tests/integration/test_admin_chatbot_config.py`
  - `tests/integration/test_scenario_bot_override_e2e.py`
  - `tests/integration/test_session_manager_config.py`
  - `docs/admin_chatbot_config_guide.md`
  - `docs/developer_chatbot_config_guide.md`
  - `docs/tutor_threshold_slider_verification.md`

### Fixed
- 시나리오 선택 후 채팅이 시작되지 않던 버그 수정
  - `GET /sessions/{id}/messages/updates` 엔드포인트 구현 (HTMX 폴링용)
  - 시나리오 접근 시 세션 자동 생성 및 `session_id` 템플릿 전달
  - chat.html JavaScript 단순화 (31줄 제거, 에러 핸들러 추가)

### Added
- `tests/unit/test_message_updates.py`: 메시지 업데이트 엔드포인트 단위 테스트 (11개)
- `tests/integration/test_chat_start_flow.py`: 세션 자동 생성 통합 테스트 (9개)
- `docs/deployment_migration_guide.md`: 챗봇 설정 마이그레이션 가이드

### Migration
- 기존 데이터베이스 설정값을 `.env`로 수동 이전 필요
- 마이그레이션 스크립트: `src/db/migrations/003_remove_chatbot_config.sql`
- 상세 가이드: `docs/deployment_migration_guide.md`

### Performance
- 설정 로드 속도 100배 개선: ~10ms → ~0.1ms (DB 조회 제거)
- 코드베이스 약 1,500줄 감소로 유지보수성 향상
- `SessionManager._load_bot_config()` 단순화 (async → sync)

## [0.8.8] - 2025-01-06

### Added
- 초기 릴리스: Misconception Dialogue Simulator
- Phase 1-2: Project setup and infrastructure
- Phase 3: MVP Dialogue System
  - Teacher authentication with session management
  - Scenario selection and dialogue interface
  - AI student bot with misconception role-play (GPT-4-turbo)
  - AI tutor bot with intervention logic (GPT-3.5-turbo)
  - Three-party real-time conversation flow
- Phase 4: Session Analysis
  - Post-dialogue question classification
  - Frequency distribution analysis
  - CSV export with anonymization
- Phase 5: Admin Scenario Management
  - CRUD operations for dialogue scenarios
  - Role-based access control (admin)
- Phase 6: Framework Configuration
  - Custom analysis framework creation
  - Dynamic label configuration (2-20 labels)
- Phase 7: Admin Session Logs
  - Session filtering and search
  - Bulk CSV export
  - Aggregated statistics dashboard
- Phase 3 (Advanced): Dynamic Configuration & Analytics
  - API usage tracking with cost analysis
  - Prompt template management with versioning
  - Dynamic prompt loading with caching

### Security
- Session-based authentication with secure cookies
- Rate limiting (slowapi)
- CORS configuration
- Security headers (X-Frame-Options, CSP, HSTS)
- Input validation (Pydantic)
- SQL injection prevention (SQLAlchemy ORM)

### Performance
- Error handling with exponential backoff (tenacity)
- SQLite WAL mode for concurrent reads
- Structured JSON logging (python-json-logger)
- Health and metrics endpoints for monitoring
