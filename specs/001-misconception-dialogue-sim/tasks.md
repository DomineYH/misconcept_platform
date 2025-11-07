# Tasks: Misconception Dialogue Simulator

**Input**: Design documents from `/specs/001-misconception-dialogue-sim/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Following TDD workflow per constitution - tests are REQUIRED before implementation

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## 버그 수정 (2025-11-07)

**문제**: 시나리오 선택 후 채팅이 시작되지 않는 현상

**근본 원인**:
1. 누락된 HTMX 폴링 엔드포인트 (`GET /sessions/{id}/messages/updates`)
2. 정의되지 않은 템플릿 변수 (`session_id` 미전달)
3. 세션 생성 흐름 불일치 (클라이언트 vs 서버)

**수정 내용**:
- [x] FIX-001: `/sessions/{id}/messages/updates` 엔드포인트 구현
- [x] FIX-002: 시나리오 접근 시 세션 자동 생성
- [x] FIX-003: chat.html JavaScript 단순화
- [x] FIX-004: HTMX 폴링 `since` 파라미터 추가
- [x] TEST-001: 단위 테스트 11개 작성 (`tests/unit/test_message_updates.py`)
- [x] TEST-002: 통합 테스트 9개 작성 (`tests/integration/test_chat_start_flow.py`)

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

-  [X] T001 Create project directory structure: src/models/, src/services/, src/api/routes/, src/templates/, src/db/, src/prompts/, tests/contract/, tests/integration/, tests/unit/, static/css/, static/js/
-  [X] T002 Initialize Python project with pyproject.toml for uv package manager, configure Black with line-length=80, ruff linter, pytest with pytest-asyncio
-  [X] T003 [P] Create .env.example file with OPENAI_API_KEY, SESSION_SECRET, DATABASE_URL, CHAT_MODEL, ANALYSIS_MODEL, HOST, PORT placeholders
-  [X] T004 [P] Create .editorconfig with max_line_length=80, charset=utf-8, end_of_line=lf
-  [X] T005 [P] Create .gitignore for Python (venv/, __pycache__/, *.db, .env)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

-  [X] T006 Create src/config.py to load environment variables using python-dotenv
-  [X] T007 Create src/db/connection.py with SQLAlchemy async engine, session factory, and Base declarative class
-  [X] T008 Implement database initialization script to execute schema creation SQL from data-model.md in src/db/init_schema.py
-  [X] T009 Create src/db/seed.py to populate default AnalysisFramework ("High/Low Leverage" with labels: Pressing, Linking, Directing, Recall), admin user, and sample scenario
-  [X] T010 [P] Create src/api/dependencies.py with get_db_session dependency and get_current_user auth dependency using session cookies
-  [X] T011 [P] Create src/api/schemas.py with Pydantic models for common request/response schemas (ErrorResponse, etc.)
-  [X] T012 Setup session middleware in src/main.py using SessionMiddleware with HttpOnly, SameSite=Lax cookies, 8-hour timeout
-  [X] T013 Create src/templates/layout.html base template with HTMX script inclusion, common navigation, and content block
-  [X] T014 [P] Create static/js/htmx.min.js by downloading HTMX library
-  [X] T015 [P] Create static/css/styles.css with basic styling (or Tailwind CSS setup if using)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Teacher Conducts Dialogue Session (Priority: P1) 🎯 MVP

**Goal**: Enable teachers to select scenarios, engage in three-party dialogue with student/tutor chatbots, receive real-time feedback

**Independent Test**: Teacher logs in with student ID + nickname, selects active scenario, asks questions triggering both student responses and tutor interventions, observes three-party conversation flow

### Tests for User Story 1 (TDD Workflow - Write FIRST, Ensure FAIL)

-  [X] T016 [P] [US1] Contract test for POST /login in tests/contract/test_auth_endpoints.py - verify session cookie creation and redirect
-  [X] T017 [P] [US1] Contract test for GET /scenarios in tests/contract/test_scenario_endpoints.py - verify active scenarios list returned
-  [X] T018 [P] [US1] Contract test for POST /sessions in tests/contract/test_session_endpoints.py - verify session creation
-  [X] T019 [P] [US1] Contract test for POST /sessions/{id}/messages in tests/contract/test_session_endpoints.py - verify message creation and chatbot responses
-  [X] T020 [P] [US1] Integration test for full dialogue flow in tests/integration/test_dialogue_flow.py - teacher login → scenario select → multi-turn dialogue with student/tutor responses
-  [X] T021 [P] [US1] Integration test for tutor intervention triggers in tests/integration/test_tutor_intervention.py - low-leverage question threshold, stagnation detection

### Database Models for User Story 1

-  [X] T022 [P] [US1] Create User model in src/models/user.py with student_uid, nickname, role, unique constraint on (student_uid, nickname)
-  [X] T023 [P] [US1] Create AnalysisFramework model in src/models/analysis_framework.py with name, description, labels_json field
-  [X] T024 [P] [US1] Create Scenario model in src/models/scenario.py with title, prompt, student_profile, is_active, framework_id foreign key
-  [X] T025 [P] [US1] Create Session model in src/models/session.py with scenario_id, teacher_id foreign keys, started_at, ended_at timestamps
-  [X] T026 [P] [US1] Create Message model in src/models/message.py with session_id foreign key, role enum, content, created_at timestamp
-  [X] T027 [P] [US1] Unit tests for User model validation in tests/unit/test_models.py - test unique constraint, role enum, field lengths
-  [X] T028 [P] [US1] Unit tests for Scenario model validation in tests/unit/test_models.py - test is_active constraint, framework_id relationship
-  [X] T029 [P] [US1] Unit tests for Session model validation in tests/unit/test_models.py - test foreign key relationships, timestamp constraints
-  [X] T030 [P] [US1] Unit tests for Message model validation in tests/unit/test_models.py - test role enum, cascade delete, content length

### LLM Services for User Story 1

-  [X] T031 [US1] Create src/prompts/student_system.txt template with misconception role-play instructions, threshold for "aha moment", student behavior constraints
-  [X] T032 [US1] Create src/prompts/tutor_system.txt template with intervention guidelines, feedback patterns, positive reinforcement examples
-  [X] T033 [P] [US1] Implement StudentBot service in src/services/student_bot.py using OpenAI GPT-4-turbo with conversation history management, scenario-specific prompt loading, temperature=0.7
-  [X] T034 [P] [US1] Implement TutorBot service in src/services/tutor_bot.py with intervention trigger logic (low-leverage threshold, stagnation detection, derailment), feedback generation
-  [X] T035 [P] [US1] Unit tests for StudentBot in tests/unit/test_student_bot.py - mock OpenAI responses, verify prompt formatting, test misconception consistency
-  [X] T036 [P] [US1] Unit tests for TutorBot in tests/unit/test_tutor_bot.py - mock OpenAI responses, verify intervention triggers, test rate limiting (max 3 per 10 questions)
-  [X] T037 [US1] Implement SessionManager service in src/services/session_mgr.py to orchestrate dialogue flow: teacher message → student response → tutor evaluation → auto-save every 30s

### API Routes for User Story 1

-  [X] T038 [US1] Implement GET /login route in src/api/routes/auth.py rendering login.html template
-  [X] T039 [US1] Implement POST /login route in src/api/routes/auth.py with student_uid/nickname validation, User creation/retrieval, session cookie generation
-  [X] T040 [US1] Implement POST /logout route in src/api/routes/auth.py clearing session cookie and redirecting to /login
-  [X] T041 [US1] Implement GET /scenarios route in src/api/routes/scenarios.py listing active scenarios (is_active=1) with title and student_profile
-  [X] T042 [US1] Implement GET /scenarios/{id} route in src/api/routes/scenarios.py rendering chat.html template with scenario details and empty message list
-  [X] T043 [US1] Implement POST /sessions route in src/api/routes/sessions.py creating Session record, returning session ID
-  [X] T044 [US1] Implement POST /sessions/{id}/messages route in src/api/routes/sessions.py accepting teacher message, invoking StudentBot and TutorBot services, returning HTML fragments via HTMX
-  [X] T045 [US1] Implement HTMX polling endpoint GET /sessions/{id}/messages/updates in src/api/routes/sessions.py returning new messages since last poll (every 2s) - ✅ 완료 (2025-11-07)

### Templates for User Story 1

-  [X] T046 [P] [US1] Create src/templates/login.html with form for student_uid and nickname fields, POST to /login
-  [X] T047 [P] [US1] Create src/templates/scenarios.html listing active scenarios with scenario selection cards
-  [X] T048 [US1] Create src/templates/chat.html with three-party dialogue interface: teacher input form, message list container with HTMX polling (hx-trigger="every 2s"), role-specific message styling
-  [X] T049 [P] [US1] Create src/templates/partials/message.html component displaying single message with role label (teacher/student/tutor) and timestamp
-  [X] T050 [US1] Wire HTMX interactions in chat.html: teacher form POST to /sessions/{id}/messages with hx-swap="beforeend" on message container, hx-indicator for loading state

**Checkpoint**: User Story 1 MVP complete - teachers can log in, select scenarios, conduct dialogues with student/tutor chatbots, observe interventions

---

## Phase 4: User Story 2 - Teacher Reviews Session Analysis (Priority: P2)

**Goal**: After completing dialogue, teacher views analysis report with question classification, frequency statistics, and downloads CSV

**Independent Test**: Complete any dialogue session, trigger session end, view analysis report with classification badges and frequency charts, download CSV file successfully

### Tests for User Story 2 (TDD Workflow - Write FIRST, Ensure FAIL)

-  [X] T051 [P] [US2] Contract test for POST /sessions/{id}/end in tests/contract/test_session_endpoints.py - verify session ending and SessionSummary return
-  [X] T052 [P] [US2] Contract test for GET /sessions/{id}/export.csv in tests/contract/test_session_endpoints.py - verify CSV download with correct headers and content
-  [X] T053 [P] [US2] Integration test for session analysis in tests/integration/test_session_analysis.py - complete dialogue → end session → verify QuestionAnalysis records created with correct labels
-  [X] T054 [P] [US2] Integration test for CSV export in tests/integration/test_csv_export.py - verify CSV format, anonymized session ID, timestamp formatting

### Database Models for User Story 2

-  [X] T055 [P] [US2] Create QuestionAnalysis model in src/models/question_analysis.py with message_id unique foreign key, label, confidence, meta_json fields
-  [X] T056 [P] [US2] Create SessionSummary model in src/models/session_summary.py with session_id unique foreign key, distribution_json, feedback, created_at timestamp
-  [X] T057 [P] [US2] Unit tests for QuestionAnalysis model in tests/unit/test_models.py - test confidence range constraint, meta_json validation, cascade delete
-  [X] T058 [P] [US2] Unit tests for SessionSummary model in tests/unit/test_models.py - test distribution_json format, unique session_id constraint

### LLM Analysis Service for User Story 2

-  [X] T059 [US2] Create src/prompts/analysis_prompt.txt template with framework-specific classification instructions, few-shot examples for high/low leverage categories
-  [X] T060 [US2] Implement Analyzer service in src/services/analyzer.py using OpenAI GPT-3.5-turbo with stateless question classification, structured JSON output, temperature=0.2
-  [X] T061 [P] [US2] Unit tests for Analyzer in tests/unit/test_analyzer.py - mock OpenAI responses, verify label matching framework, test confidence scoring

### Export Service for User Story 2

-  [X] T062 [US2] Implement CSVExporter service in src/services/export.py generating UTF-8 CSV with columns: session_id, scenario_title, student_hash, timestamp, role, content, label, confidence, feedback
-  [X] T063 [US2] Add anonymization logic to CSVExporter using SHA-256 hash with session-specific salt for student_uid
-  [X] T064 [US2] Add session summary row to CSV output with distribution and feedback in feedback column
-  [X] T065 [P] [US2] Unit tests for CSVExporter in tests/unit/test_export.py - verify CSV format, test anonymization, verify summary row inclusion

### API Routes for User Story 2

-  [X] T066 [US2] Implement POST /sessions/{id}/end route in src/api/routes/sessions.py updating Session.ended_at timestamp, triggering Analyzer for all teacher messages, generating SessionSummary
-  [X] T067 [US2] Implement GET /sessions/{id}/analysis route in src/api/routes/sessions.py rendering analysis report HTML with question list, classification badges, frequency chart
-  [X] T068 [US2] Implement GET /sessions/{id}/export.csv route in src/api/routes/sessions.py using CSVExporter to generate and return CSV file download

### Templates for User Story 2

-  [X] T069 [P] [US2] Create src/templates/analysis.html displaying session analysis with question list showing type badges (high/low leverage), frequency bar chart visualization
-  [X] T070 [P] [US2] Create src/templates/partials/analysis_bar.html component for frequency distribution chart using HTML/CSS or chart library
-  [X] T071 [US2] Add "End Session" button to chat.html template with POST to /sessions/{id}/end redirecting to analysis page

**Checkpoint**: User Story 2 complete - teachers can end sessions, view detailed analysis reports with question classifications and frequency statistics, download CSV exports

---

## Phase 5: User Story 3 - Admin Manages Scenarios (Priority: P3)

**Goal**: Administrator creates, edits, and activates/deactivates dialogue scenarios with misconception profiles

**Independent Test**: Admin logs in, creates new scenario with misconception details and problem context, activates it, verifies it appears in teacher's scenario list

### Tests for User Story 3 (TDD Workflow - Write FIRST, Ensure FAIL)

-  [X] T072 [P] [US3] Contract test for GET /admin in tests/contract/test_admin_endpoints.py - verify admin dashboard access with role check
-  [X] T073 [P] [US3] Contract test for POST /admin/scenarios in tests/contract/test_admin_endpoints.py - verify scenario creation with validation
-  [X] T074 [P] [US3] Contract test for PUT /admin/scenarios/{id} in tests/contract/test_admin_endpoints.py - verify scenario update and active status toggle
-  [X] T075 [P] [US3] Integration test for scenario lifecycle in tests/integration/test_scenario_management.py - create → activate → verify visibility → deactivate → verify hidden

### API Routes for User Story 3

-  [X] T076 [US3] Implement GET /admin route in src/api/routes/admin.py rendering admin dashboard with role=admin check, showing scenario count and session statistics
-  [X] T077 [US3] Implement GET /admin/scenarios route in src/api/routes/admin.py listing all scenarios (active and inactive) with edit/toggle controls
-  [X] T078 [US3] Implement POST /admin/scenarios route in src/api/routes/admin.py creating new Scenario with validation (title 3-200 chars, prompt 10-10000 chars)
-  [X] T079 [US3] Implement PUT /admin/scenarios/{id} route in src/api/routes/admin.py updating scenario fields or toggling is_active status
-  [X] T080 [US3] Add authorization check to admin routes preventing modification of scenarios with active sessions (Session.ended_at IS NULL)

### Templates for User Story 3

-  [X] T081 [P] [US3] Create src/templates/admin/dashboard.html displaying aggregate metrics: total scenarios, active scenarios, total sessions, average session duration
-  [X] T082 [P] [US3] Create src/templates/admin/scenarios.html listing scenarios with inline edit forms, active toggle switches, create new scenario form
-  [X] T083 [US3] Add admin navigation link to layout.html visible only for users with role=admin

**Checkpoint**: User Story 3 complete - admins can create, edit, and manage scenario availability, scenarios appear/disappear in teacher interface based on active status

---

## Phase 6: User Story 4 - Admin Configures Analysis Framework (Priority: P4)

**Goal**: Administrator selects and applies analysis framework defining question categorization rules

**Independent Test**: Admin selects alternative analysis framework from options, applies it, verifies subsequent sessions use new classification scheme

### Tests for User Story 4 (TDD Workflow - Write FIRST, Ensure FAIL)

- [x] T084 [P] [US4] Contract test for GET /admin/frameworks in tests/contract/test_admin_endpoints.py - verify framework list display ✅
- [x] T085 [P] [US4] Contract test for POST /admin/frameworks in tests/contract/test_admin_endpoints.py - verify new framework registration with labels validation ✅
- [x] T086 [P] [US4] Integration test for framework switching in tests/integration/test_framework_switching.py - create framework → apply to scenario → verify classifications use new labels ✅

### API Routes for User Story 4

- [x] T087 [US4] Implement GET /admin/frameworks route in src/api/routes/admin.py listing all AnalysisFramework records with name, description, labels ✅
- [x] T088 [US4] Implement POST /admin/frameworks route in src/api/routes/admin.py creating new AnalysisFramework with labels_json validation (2-20 labels, each 2-50 chars) ✅
- [x] T089 [US4] Add framework selection to scenario edit form in PUT /admin/scenarios/{id} allowing framework_id change ✅

### Templates for User Story 4

- [x] T090 [P] [US4] Create src/templates/admin/frameworks.html listing frameworks with category definitions, create new framework form with dynamic label input fields ✅
- [x] T091 [US4] Add framework dropdown to scenario edit form in admin/scenarios.html showing available frameworks ✅

**Checkpoint**: ✅ User Story 4 complete - admins can register custom analysis frameworks, apply them to scenarios, new sessions use updated classification categories

---

## Phase 7: User Story 5 - Admin Reviews Session Logs (Priority: P5)

**Goal**: Administrator views aggregated statistics, searches/filters session logs, downloads CSV exports for research

**Independent Test**: Admin accesses session log dashboard, applies date range and user filters, views aggregated metrics, downloads filtered CSV results

### Tests for User Story 5 (TDD Workflow - Write FIRST, Ensure FAIL)

-  [X] T092 [P] [US5] Contract test for GET /admin/sessions in tests/contract/test_admin_endpoints.py - verify session list with filtering parameters
-  [X] T093 [P] [US5] Contract test for GET /admin/sessions/export in tests/contract/test_admin_endpoints.py - verify bulk CSV export for multiple sessions
-  [X] T094 [P] [US5] Integration test for session filtering in tests/integration/test_session_filtering.py - create sessions with various dates/users → apply filters → verify correct subset returned

### API Routes for User Story 5

-  [X] T095 [US5] Implement GET /admin/sessions route in src/api/routes/admin.py with query parameters for date_from, date_to, teacher_id filters, returning paginated session list
-  [X] T096 [US5] Implement GET /admin/sessions/export route in src/api/routes/admin.py generating bulk CSV export for filtered sessions with anonymized identifiers
-  [X] T097 [US5] Add aggregated statistics endpoint GET /admin/stats route returning total sessions, average question counts, leverage ratio distributions

### Templates for User Story 5

-  [X] T098 [P] [US5] Create src/templates/admin/sessions.html with filter controls (date range picker, user dropdown), session list table showing scenario, teacher, start/end times, question count
-  [X] T099 [US5] Add statistics dashboard to admin/dashboard.html showing charts for session trends, average durations, leverage ratio distribution

**Checkpoint**: User Story 5 complete - admins have full visibility into session logs, can filter/search by criteria, export data for research analysis

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and production readiness

-  [X] T100 [P] Add comprehensive error handling across all routes with user-friendly error messages and logging to src/api/routes/*.py
-  [X] T101 [P] Implement rate limiting for LLM API calls with exponential backoff in src/services/student_bot.py and src/services/tutor_bot.py
-  [X] T102 [P] Enable SQLite WAL mode in src/db/connection.py for improved concurrent read performance
-  [X] T103 [P] Add structured logging with JSON format for production in src/main.py using Python logging module
-  [X] T104 [P] Configure CORS and security headers in src/main.py for production deployment
-  [X] T105 [P] Create production deployment guide in docs/deployment.md with uvicorn --workers 4 configuration, nginx reverse proxy setup
-  [X] T106 [P] Add monitoring endpoints GET /health and GET /metrics in src/api/routes/health.py for production observability
-  [X] T107 Code review and refactoring pass: verify all files under 300 lines, all lines under 80 characters per constitution
-  [X] T108 [P] Update README.md with project overview, installation instructions, development workflow
-  [X] T109 Run through quickstart.md validation: setup → first dialogue session → analysis report → CSV export
-  [X] T110 [P] Add pre-commit hooks for Black formatting and ruff linting in .pre-commit-config.yaml
-  [X] T111 [P] Performance optimization: add caching for prompt templates with @lru_cache, optimize database queries for N+1 issues
-  [X] T112 [P] Security hardening: verify HTTPS enforcement for production, audit session cookie settings, review for SQL injection risks

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 components but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent CRUD operations for scenarios
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Extends US3 scenario management with framework selection
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Read-only admin reporting, no dependencies

### Within Each User Story (TDD Workflow)

1. Write contract tests FIRST, ensure they FAIL
2. Write unit tests for models/services FIRST, ensure they FAIL
3. Implement models (marked [P] can run in parallel)
4. Implement services (depends on models)
5. Implement API routes (depends on services)
6. Implement templates (marked [P] can run in parallel)
7. Run tests, ensure they PASS
8. Integration tests verify full story workflow

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003, T004, T005)
- All Foundational tasks marked [P] can run in parallel (T010, T011, T014, T015)
- Within each user story:
  - All contract tests marked [P] can run in parallel
  - All unit tests marked [P] can run in parallel
  - All models marked [P] can be implemented in parallel
  - All services marked [P] can be implemented in parallel
  - All templates marked [P] can be created in parallel
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All Polish tasks marked [P] can run in parallel (T100-T112)

---

## Parallel Example: User Story 1

```bash
# Launch all contract tests for User Story 1 together:
Task T016: "Contract test for POST /login in tests/contract/test_auth_endpoints.py"
Task T017: "Contract test for GET /scenarios in tests/contract/test_scenario_endpoints.py"
Task T018: "Contract test for POST /sessions in tests/contract/test_session_endpoints.py"
Task T019: "Contract test for POST /sessions/{id}/messages in tests/contract/test_session_endpoints.py"

# Launch all model implementations for User Story 1 together:
Task T022: "Create User model in src/models/user.py"
Task T023: "Create AnalysisFramework model in src/models/analysis_framework.py"
Task T024: "Create Scenario model in src/models/scenario.py"
Task T025: "Create Session model in src/models/session.py"
Task T026: "Create Message model in src/models/message.py"

# Launch all LLM services for User Story 1 together:
Task T033: "Implement StudentBot service in src/services/student_bot.py"
Task T034: "Implement TutorBot service in src/services/tutor_bot.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T015) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T016-T050)
4. **STOP and VALIDATE**: Test User Story 1 independently - teacher can conduct full dialogue session
5. Deploy/demo MVP if ready

**MVP Scope**: Teachers can log in, select scenarios, engage in realistic three-party dialogues with AI student/tutor chatbots, receive pedagogical feedback through tutor interventions

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → **Deploy/Demo MVP** (core dialogue experience)
3. Add User Story 2 → Test independently → Deploy/Demo (adds reflective analysis)
4. Add User Story 3 → Test independently → Deploy/Demo (adds content management)
5. Add User Story 4 → Test independently → Deploy/Demo (adds framework customization)
6. Add User Story 5 → Test independently → Deploy/Demo (adds research analytics)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (dialogue core)
   - Developer B: User Story 2 (analysis reporting)
   - Developer C: User Story 3 (scenario management)
3. Stories complete and integrate independently
4. Developer D can work on User Stories 4 & 5 after US3 completes

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- **TDD Workflow**: Verify tests FAIL before implementing, then ensure they PASS after implementation
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution compliance: Verify all files ≤300 lines, all lines ≤80 characters during code reviews
- LLM API calls: Implement error handling and retry logic, mock responses in tests for deterministic results
- HTMX polling: 2s interval acceptable for MVP, migrate to WebSockets if real-time becomes critical
- Session auto-save: 30s interval prevents data loss during network interruptions
