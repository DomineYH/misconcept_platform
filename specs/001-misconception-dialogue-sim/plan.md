# Implementation Plan: Misconception Dialogue Simulator

**Branch**: `001-misconception-dialogue-sim` | **Date**: 2025-11-05 |
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from
`/specs/001-misconception-dialogue-sim/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command.
See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a three-party dialogue simulator where teachers practice
pedagogical questioning with AI-powered student chatbots exhibiting
misconceptions, while tutor chatbots intervene to guide conversation
quality. System analyzes teacher questions using configurable
pedagogical frameworks (high/low leverage moves), provides session
reports with frequency statistics, and exports to CSV for research.

## Implementation Status

**Last Updated**: 2025-11-05
**Progress**: 83/112 tasks (74.1%)
**Current Phase**: Phase 6 Complete ✅, Phase 7 Ready to Start

### Completed Phases

✅ **Phase 1: Setup** (5/5 tasks - 100%)
- Project structure, pyproject.toml, .env.example, .editorconfig,
  .gitignore

✅ **Phase 2: Foundational** (10/10 tasks - 100%)
- config.py, database connection, schema initialization, seed data
- API dependencies, Pydantic schemas, FastAPI app with middleware
- Base templates, HTMX library, basic CSS

✅ **Phase 3: User Story 1 - MVP Dialogue** (35/35 tasks - 100%)
- Tests: Contract (6) + Integration (2) + Unit (4)
- Models: User, AnalysisFramework, Scenario, Session, Message
- Services: StudentBot, TutorBot, SessionManager
- Routes: Authentication, Scenarios, Sessions (8 endpoints)
- Templates: login, scenarios, chat with HTMX integration

✅ **Phase 4: User Story 2 - Session Analysis** (13/13 tasks - 100%)
- Models: QuestionAnalysis, SessionSummary
- Services: Analyzer (LLM classification), CSVExporter (anonymization)
- Routes: POST /sessions/{id}/end, GET /sessions/{id}/analysis,
  GET /sessions/{id}/analysis_page, GET /sessions/{id}/export.csv
- Templates: analysis.html, partials/analysis_bar.html
- Tests: Unit tests for Analyzer (10) and CSVExporter (12)

✅ **Phase 5: User Story 3 - Admin Manages Scenarios** (12/12 tasks - 100%)
- Tests: Contract (11) + Integration (2)
- Routes: GET /admin, GET/POST/PUT /admin/scenarios
- Templates: admin/dashboard.html, admin/scenarios.html
- Role-based access control, active/inactive management
- T080 protection for scenarios with active sessions

✅ **Phase 6: User Story 4 - Framework Configuration** (8/8 tasks - 100%)
- Tests: Contract (10) + Integration (2)
- Routes: GET/POST /admin/frameworks with label validation
- Template: admin/frameworks.html with dynamic label inputs
- Framework switching capability, Pydantic V2 migration
- T080 protection for framework changes

### Current Phase

🔜 **Phase 7: User Story 5 - Admin Reviews Session Logs** (0/8 tasks)
- Ready to implement: Session list with filtering, aggregated statistics
- Dependencies met: All admin routes and models complete
- Independent: Phase 8 polish tasks can start in parallel

**Detailed Progress**: See [progress.md](./progress.md)
**Phase 3 Details**: See [phase3-complete.md](./phase3-complete.md)
**Phase 4 Details**: See [phase4-complete.md](./phase4-complete.md)
**Phase 5 Details**: See [phase5-complete.md](./phase5-complete.md)
**Phase 6 Details**: See [phase6-complete.md](./phase6-complete.md)

## Technical Context

**Language/Version**: Python 3.11+ (uv package manager)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Jinja2, HTMX,
Tailwind CSS (optional), OpenAI SDK
**Storage**: SQLite3 (single-file database for simplicity)
**Testing**: pytest (unit/integration/contract tests per TDD workflow)
**Target Platform**: Linux server (uvicorn ASGI server)
**Project Type**: Web application (server-side rendering + REST API)
**Performance Goals**: <2s average response latency for LLM calls, 100
concurrent sessions support
**Constraints**: Cookie-based auth (student ID + nickname), minimal
personal data collection, 30s auto-save intervals
**Scale/Scope**: Educational research tool, expected 50-200 concurrent
users, 5-20 scenarios per deployment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1
design.*

### Principle I: File Length Discipline (300 lines max)

**Gate**: ✅ PASS (with monitoring)

**Analysis**:
- Database models: 7 tables × ~30 lines/model = ~210 lines → Split
  into separate model files
- API routes: 11 endpoints → Group by domain (auth, scenarios, sessions,
  admin) across 4 route files
- LLM service: Student/tutor/analysis logic → Separate service modules
- Template rendering: Jinja templates naturally modular

**Enforcement Strategy**:
- Use SQLAlchemy declarative models, one model per file in `src/models/`
- Group related routes (max 3-4 endpoints per file) in `src/api/routes/`
- Separate LLM concerns: `src/services/student_bot.py`,
  `src/services/tutor_bot.py`, `src/services/analyzer.py`
- Jinja template partials for reusable components

### Principle II: Line Length Standard (80 characters max)

**Gate**: ✅ PASS

**Analysis**:
- Python code: Use Black formatter with 80-char line length
- SQL queries: Multi-line formatting with proper indentation
- Jinja templates: Break long template expressions across lines
- Configuration: YAML/TOML naturally supports multi-line

**Enforcement Strategy**:
- Configure Black: `line-length = 80` in pyproject.toml
- Use `ruff` linter with line-length check
- Pre-commit hooks enforce formatting
- Editor config: `.editorconfig` with `max_line_length = 80`

### Principle III: Test-First Development (NON-NEGOTIABLE)

**Gate**: ✅ PASS (workflow defined)

**Analysis**:
- Contract tests: API endpoint schemas with OpenAPI validation
- Integration tests: Database transactions, LLM mocking, session flows
- Unit tests: Model validation, service logic, prompt templates

**TDD Workflow**:
1. Write failing contract test for endpoint (e.g., `POST /messages`)
2. Write failing unit test for service logic (e.g., message creation)
3. Implement minimum code to pass tests
4. Write integration test for full flow (teacher → student → tutor)
5. Refactor with confidence (tests provide safety net)

**Test Structure**:
```
tests/
├── contract/
│   ├── test_auth_endpoints.py
│   ├── test_scenario_endpoints.py
│   └── test_session_endpoints.py
├── integration/
│   ├── test_dialogue_flow.py
│   ├── test_tutor_intervention.py
│   └── test_session_analysis.py
└── unit/
    ├── test_models.py
    ├── test_student_bot.py
    ├── test_tutor_bot.py
    └── test_analyzer.py
```

## Project Structure

### Documentation (this feature)

```text
specs/001-misconception-dialogue-sim/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── auth.yaml
│   ├── scenarios.yaml
│   ├── sessions.yaml
│   └── admin.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── models/              # SQLAlchemy ORM models (one per file)
│   ├── user.py
│   ├── scenario.py
│   ├── session.py
│   ├── message.py
│   ├── analysis_framework.py
│   ├── question_analysis.py
│   └── session_summary.py
├── services/            # Business logic and LLM integration
│   ├── student_bot.py   # Student chatbot logic
│   ├── tutor_bot.py     # Tutor intervention logic
│   ├── analyzer.py      # Question classification
│   ├── session_mgr.py   # Session lifecycle management
│   └── export.py        # CSV export generation
├── api/                 # FastAPI routes and dependencies
│   ├── routes/
│   │   ├── auth.py      # Login/logout
│   │   ├── scenarios.py # Scenario selection
│   │   ├── sessions.py  # Dialogue and messages
│   │   └── admin.py     # Admin CRUD operations
│   ├── dependencies.py  # Auth, DB session injection
│   └── schemas.py       # Pydantic request/response models
├── templates/           # Jinja2 HTML templates
│   ├── layout.html      # Base template
│   ├── login.html
│   ├── scenarios.html
│   ├── chat.html        # Three-party dialogue UI
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── scenarios.html
│   │   └── frameworks.html
│   └── partials/
│       ├── message.html      # Single message component
│       └── analysis_bar.html # Frequency chart
├── db/                  # Database utilities
│   ├── connection.py    # SQLAlchemy engine/session
│   └── migrations/      # Alembic migration scripts (if used)
├── prompts/             # LLM prompt templates
│   ├── student_system.txt    # Student bot system prompt
│   ├── tutor_system.txt      # Tutor bot system prompt
│   └── analysis_prompt.txt   # Classification prompt
├── config.py            # Environment variable loading
└── main.py              # FastAPI application entry point

tests/
├── contract/
│   ├── test_auth_endpoints.py
│   ├── test_scenario_endpoints.py
│   ├── test_session_endpoints.py
│   └── test_admin_endpoints.py
├── integration/
│   ├── test_dialogue_flow.py       # Full teacher-student-tutor cycle
│   ├── test_tutor_intervention.py  # Intervention triggers
│   ├── test_session_analysis.py    # Question classification
│   └── test_csv_export.py          # CSV generation
└── unit/
    ├── test_models.py
    ├── test_student_bot.py
    ├── test_tutor_bot.py
    ├── test_analyzer.py
    └── test_session_mgr.py

static/                  # Static assets (CSS, JS)
├── css/
│   └── styles.css       # Tailwind build output or custom CSS
└── js/
    └── htmx.min.js      # HTMX for partial updates
```

**Structure Decision**: Web application structure selected based on
FastAPI + server-side rendering requirements. Single `src/` directory
for backend code with separate `templates/` for Jinja2, `static/` for
assets, and `tests/` mirroring source structure. No separate
frontend/backend split since SSR eliminates need for distinct frontend
build process.

## Complexity Tracking

> **No violations detected** — all constitution principles can be
> satisfied with proposed structure and enforcement strategies.
