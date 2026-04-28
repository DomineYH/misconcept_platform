# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1.0] - 2026-04-28

### Fixed
- 프레임워크 삭제 시 `question_analysis.message_id NOT NULL constraint failed`
  500 에러 (closes #35)
  - 원인: `Message.question_analysis` 관계에 cascade 옵션이 누락되어 ORM이
    Session→Message cascade 삭제 시 자식 QuestionAnalysis 의 FK 를 NULL 로
    UPDATE 하려다 NOT NULL 위반
  - 수정: `src/models/message.py` 의 `question_analysis` relationship 에
    `cascade="all, delete-orphan"` 추가 (기존 `Session.messages`/
    `Session.summary` 와 동일 패턴)
  - DB 스키마/마이그레이션 변경 없음
  - 회귀 테스트: `tests/integration/test_admin_framework_delete.py` (3 케이스)

## [0.4.0.0] - 2026-04-28

### Added
- 분석 상세화면 코칭 친화적 3탭 UI 재설계 (closes #33)
  - 기존 "질문별 분석 보기" 토글이 "상세 분석" + 3탭(대화코칭/우수한 점/
    개선할 점)으로 교체
  - 대화코칭 탭: 전체 대화 시간순 노출, 교사 메시지에 level 기반 색상
    (잘 한 대화/놓친 순간 라벨)
  - 개선할 점 탭: low 등급 카드에 LLM이 작성한 "개선한 문장" 표시
  - 키보드 네비게이션: ←/→/Home/End/ESC
  - 분석 응답에 `messages` 타임라인 + `framework_label_criteria` 추가
- Framework 상위 카테고리(category_name) + 라벨 수준(level: high/low) 기능 (closes #30)
  - `analysis_framework.category_name` 컬럼 추가 (nullable)
  - 라벨 dict에 `level` 키 추가 (`"high"` / `"low"` / `null`)
  - `question_analysis.grade` 컬럼 추가 (우수/개선, 분석 시점 스냅샷)
  - Admin UI: 카테고리 이름 입력 + 라벨별 수준 드롭다운
  - 분석 화면: 등급 뱃지(우수/개선) + 분포 차트 그룹 카운트
  - 마이그레이션 022 (UP/DOWN) + `labels_grade_map` 프로퍼티

### Changed
- 분석 LLM 응답 구조 슬림화 (#33)
  - `DetailedReasoning`이 `summary` + `improved_sentence` 두 필드만 유지
  - `PedagogicalAnalysis`/`CognitiveAnalysis`/`ContextualAnalysis` 클래스 삭제
  - 분석 프롬프트가 라벨별 `level` 정보를 LLM에 전달 (low 등급에서만
    `improved_sentence` 작성)
  - Legacy `meta_json`(영역별 3블록 포함)은 정규화 단계에서 자연 폐기 —
    DB 마이그레이션 불필요
- 코치 탭의 메시지 색상은 persisted `grade`에서 derive (framework 라벨
  level 변경 시에도 historical 세션 일관성 유지)

## [0.3.0.0] - 2026-04-27

### Added
- Session analysis report redesign: brief feedback + 4 stat cards
  + collapsible detail (closes #28)
  - New `session_feedback_report` table for structured coaching
    payload (migration 019)
  - LLM synthesis service with quality validation (verbatim quotes,
    message_id integrity, length bounds)
  - Admin regenerate endpoint for re-running analysis (auth +
    rate-limit + EXCLUSIVE lock + synthesize-first-then-replace)
  - UI event logging for engagement metrics (migration 021)
  - `ApiUsageLog.operation` column for classification/synthesis/
    greeting cost separation (migration 020)
  - PRAGMA `foreign_keys=ON` applied to all SQLite connections for
    test/prod fidelity
  - Test infrastructure: `synthesis_mock`, `authenticated_async_client`,
    `test_admin` fixtures in conftest.py
  - Quality gate eval harness at `evals/issue-28/`

### Fixed
- Cross-engine FK violations in legacy tests exposed by PRAGMA
  fk=ON (test_framework_delete, test_message_updates,
  test_full_dialogue_flow) — replaced fixture shadowing with
  inline template creation in same engine
- Regeneration now preserves an existing `ok` analysis report when
  the new synthesis returns `degraded` (brief feedback present but
  empty strengths/improvements). Previously only `failed` was
  preserved; `degraded` could overwrite a richer trustworthy report.
  Returns `regeneration_status: "degraded_skipped_preserved"`.

## [0.2.3.0] - 2026-04-23

### Changed
- 채팅 화면 상단 액션 버튼을 단일 버튼으로 통합 (closes #24)
  - `대화 종료` + `분석하기` 두 버튼을 `대화 종료 후 분석 보기` 단일 primary 버튼으로 합쳐, 클릭 한 번으로 세션 종료 → 분석 호출이 자동으로 이어짐
  - 버튼 라벨이 `대화 종료 후 분석 보기 → 분석 준비 중... → 분석 중... → 분석 다시 보기` 순으로 전이되는 상태머신(`data-state=active/ending/analyzing/done/ready-to-analyze`)
  - 분석 완료 후 `분석 다시 보기`로 모달 재열람 가능, 실패 시 `분석 보기`로 복귀해 재시도 가능
  - `aria-busy`, 인라인 스피너, 부드러운 색상 전이로 로딩 상태를 시각·보조기술 모두에 전달
  - `src/templates/chat.html` 안내 문구(tab-guide)를 신규 버튼 라벨에 맞춰 갱신
  - 중복 클릭 방지 및 기존 AUTH_EXPIRED / CSRF 경로 보존

### Fixed
- 분석 모달 로딩 경쟁 조건 해소 (codex P2 follow-up, `a45e400`)
  - `/sessions/{id}/analyze` 성공 직후 상태를 `done`으로 전환하기 전에 `htmx.ajax('GET', '.../analysis_modal')` 응답을 대기하도록 `.then()` 내부로 이동
  - 모달 GET 실패 시 `.catch()`에서 `ready-to-analyze`로 되돌리고 기존 안내 alert를 재사용해 재시도 보장

### Added
- `tests/contract/test_unified_session_button.py` 계약 테스트 5종 (구 `#analyze-btn` 제거, 신 라벨/클래스/`data-state` 존재, 안내 문구 전환, `#return-to-scenarios-btn` 보존)
- `static/css/styles.css` `omc-i24-spin` 키프레임과 `#end-session-btn[aria-busy="true"]::before` 스피너, 상태별 전이 룰 (라이트·다크 모두 `currentColor`)

## [0.2.2.0] - 2026-04-19

### Fixed
- 관리자 시드 과정에서 발생하던 다중 워커 동시 기동 경쟁 조건 제거
  - `_ensure_default_group`, `ensure_default_admin_user`의 `SELECT → INSERT` 패턴을 `INSERT OR IGNORE`로 변경해 두 워커가 동시에 기본 그룹 / 기본 관리자 계정을 생성해도 UNIQUE 제약 위반으로 부팅이 실패하지 않음
  - `INSERT OR IGNORE` 이후 정식 row를 다시 읽어 경쟁에서 진 워커가 승자 row를 기준으로 후속 로직을 수행
- 기본 관리자 시드가 기존 비관리자 `admin` 사용자를 조용히 관리자로 승격시키던 보안 문제 차단
  - 이미 `admin` 이름으로 teacher 역할 사용자가 존재할 경우 시드 경로가 역할 / 비밀번호를 절대 덮어쓰지 않음
  - 역할이 이미 `admin`인 row에 한해 비밀번호 해시가 비어 있을 때만 재시드 (잠금 해제 복구 경로는 유지)

### Added
- `BOOTSTRAP_ADMIN_ON_STARTUP` 설정 플래그 (기본 `false`) 도입
  - FastAPI lifespan에서 기본 관리자 부트스트랩을 수행할지 여부를 환경 변수로 선택 가능
  - 읽기 전용 DB 역할이나 별도 시드 잡을 사용하는 프로덕션 배포가 부팅 시 실패하지 않도록 기본 비활성화
  - `src/config.py`의 `parse_testing` validator를 `parse_bool`로 일반화해 두 플래그 모두 처리
- 경쟁 조건 / 권한 승격 / 복구 경로 회귀 테스트 3종 추가 (`tests/unit/test_seed_default_admin.py`)

## [0.2.1.1] - 2026-04-19

### Removed
- dead CSS: `.messages-list`, `.message-item`, `.message-role` (역할 중첩 포함), `.message-time`, `.message-content` 계열 삭제 (#17)
  - `static/css/styles.css` 52줄 정리 (사용처 0건 확인)
  - 실제 사용 중인 역할 셀렉터 `.message-teacher/.message-student/.message-tutor/.message-mentor` 및 `.message-bubble/.message-sender/.message-content-wrapper`는 그대로 유지

## [0.2.1.0] - 2026-04-18

### Changed
- 채팅창 학생(지수)과 멘토 메시지가 시각적으로 명확히 구분됩니다 (#15)
  - 멘토 메시지: 연한 파란 배경에 짙은 파란 포인트 바, 파란 이름 레이블
  - 학생 메시지: 흰 배경에 회색 테두리
  - 다크 모드에서 역할별 색상이 자동으로 대응 (라이트/다크 각 12개 토큰)

### Fixed
- 다크 모드에서 멘토 메시지 배경이 밝은 회색으로 노출되던 버그 해소 (#15)
  - 이전: `#f3f4f6` 하드코딩이 다크 테마에 그대로 누출되어 대비가 깨짐
  - 이후: 다크 모드에서 `#1A2A3D` 네이비 배경 + 밝은 파란 액센트로 정상 렌더

## [0.2.0.0] - 2026-04-18

### Added
- 시나리오 인사말(greeting) 기능 (#12)
  - 시나리오별 멘토 인사말 텍스트 저장 (최대 5000자)
  - 관리자 시나리오 생성/수정 폼에 "인사말" 필드 추가
  - 채팅 진입 시 채팅창 최상단에 멘토 스타일 메시지로 인사말 표시
  - 인사말이 없으면(NULL/빈 문자열) 컨테이너 미출력
  - 템플릿 전용 렌더링: message 테이블에 저장되지 않으며
    분석/튜터봇/학생봇 프롬프트에 주입되지 않음
- greeting_message 컬럼 추가 마이그레이션 (018)
- 6개 Success Criteria 회귀 테스트 (12건)

### Fixed
- 관리자 편집 폼에서 인사말 필드를 비워 저장해도 기존 값이
  유지되던 버그 수정: 빈 textarea는 이제 빈 문자열로 전송되어
  백엔드 strip→None 경로로 정상 삭제됨

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
