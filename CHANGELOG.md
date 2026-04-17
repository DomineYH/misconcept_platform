# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1.1] - 2026-04-14

### Changed
- 챗봇 화면 탭 레이블 문구를 명확하게 수정 (#5)
  - "학생 프로필" → "학생 정보"
  - "학습 상황" → "문제 상황"
  - 안내 문구 및 빈 상태 메시지 일관성 반영

## [0.1.1.0] - 2026-04-11

### Added
- About 페이지: 개발자/관리자 프로필 등록 및 모달 표시
  - Contributor 모델, 마이그레이션, CRUD API 엔드포인트
  - 관리자 전용 등록/수정/삭제 관리 페이지
  - 모든 페이지에서 "about" 버튼 클릭으로 모달 표시
  - 비로그인 사용자도 about 모달 접근 가능
- Contract 테스트 8건 (생성, 수정, 삭제, 권한, 유효성 검증)

### Fixed
- pytest-asyncio 호환성 수정 (deprecated event_loop fixture 제거)
- 관리자 편집 시 phone/email 필드 초기화 불가 버그 수정
- Bio 데이터 다중행 손상 방지 (data-attribute → JSON script 태그)
- 모달 로더 에러 응답 캐싱 방지
- 마이그레이션 016 주석으로 인한 CREATE TABLE 스킵 수정

### Changed
- .gitignore에 *.db 패턴 추가

## [0.1.0.1] - 2026-04-11

### Fixed
- CSV 일괄 업로드 ��� 구분자 자동 감지 (탭, 세미콜론 지원)
- BOM 중복 시 첫 번째 컬럼 인식 실패 문제 해결
- 한국어 컬럼명(사용자, 닉네임 등)을 영문 컬럼명으로 자동 변환
- 필수 컬럼 누락 에러 메시지에 발견된 컬럼명 표시

## [0.1.0.0] - 2026-04-11

### Added
- CSV 기반 일괄 사용자 추가 기능
  - CSV 양식 다운로드 (username, nickname, role, group)
  - 업로드 후 미리보기에서 검증 결과 확인 (중복 ID, 없는 그룹, 형식 오류)
  - 미리보기에서 역할/그룹 일괄 및 개별 지정
  - 미리보기에서 행 추가, 수정, 삭제 가능
  - 등록 결과 성공/실패 카운트 및 실패 사유 표시
- 3개 API 엔드포인트: GET /admin/users/bulk/template, POST /admin/users/bulk/preview, POST /admin/users/bulk/register
- 서비스 모듈 admin_user_bulk.py (CSV 파싱, 검증, 등록)
- 33개 테스트 (스키마 7, 파싱 8, 검증 8, 등록 3, 엔드포인트 7)

### Fixed
- 관리자 API를 POST로 통일하고 세션 날짜 필터 422 에러 수정
- 세션 관리 페이지에서 시나리오 필터링 기능 제거 (성능 개선)
- 코드베이스 이모지 제거 및 세션 관리 페이지 코드 정리

### Security
- 일괄 등록 시 savepoint 패턴으로 개별 실패 격리 (전체 롤백 방지)
- CSV 미리보기 innerHTML XSS 방지 (escHtml 헬퍼)
- 등록 엔드포인트에 서버사이드 입력 검증 추가
- BulkRegisterRequest 최대 100명 제한

### Removed
- 이전 일괄 사용자 생성 코드 (패턴 모드, 직접 CSV 모드) 620줄 제거

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
