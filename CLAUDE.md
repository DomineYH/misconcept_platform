# misconcept_platform Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-05

## Implementation Status

**Feature**: 001-misconception-dialogue-sim
**Progress**: 75/112 tasks (67.0%)
**Phase**: Phase 5 Complete ✅, Phase 6 Ready 🔜

### Completed
- ✅ Phase 1: Project setup and configuration (5/5 tasks)
- ✅ Phase 2: Core infrastructure (10/10 tasks)
- ✅ Phase 3: User Story 1 - MVP Dialogue System (35/35 tasks)
  - Tests (contract + integration + unit)
  - Models (User, AnalysisFramework, Scenario, Session, Message)
  - LLM Services (StudentBot, TutorBot, SessionManager)
  - API Routes (auth, scenarios, sessions)
  - Templates (login, scenarios, chat with HTMX)
- ✅ Phase 4: User Story 2 - Session Analysis (13/13 tasks)
  - Models (QuestionAnalysis, SessionSummary)
  - Services (Analyzer, CSVExporter)
  - API Routes (session ending, analysis, CSV export)
  - Templates (analysis page, bar chart visualization)
  - Unit tests for Analyzer and CSVExporter
- ✅ Phase 5: User Story 3 - Admin Manages Scenarios (12/12 tasks)
  - Tests (contract + integration: 13 tests, all passing)
  - API Routes (admin dashboard, scenario CRUD)
  - Templates (admin dashboard, scenario management UI)
  - Role-based access control (403 for non-admin)
  - Active/inactive scenario management
  - Protection against modifying scenarios with active sessions

### Next Phase
- 🔜 Phase 6: User Story 4 - Admin Configures Analysis Framework (0/8 tasks)

**Details**: See `specs/001-misconception-dialogue-sim/progress.md`
**Phase 3 Summary**: See `specs/001-misconception-dialogue-sim/phase3-complete.md`
**Phase 4 Summary**: See `specs/001-misconception-dialogue-sim/phase4-complete.md`
**Phase 5 Summary**: See `specs/001-misconception-dialogue-sim/phase5-complete.md`

## Active Technologies

- Python 3.11+ (uv package manager)
- FastAPI (web framework)
- SQLAlchemy 2.x (async ORM)
- Jinja2 (server-side templates)
- HTMX (frontend interactivity)
- SQLite3 (database)
- OpenAI SDK (LLM integration)

## Project Structure

```text
src/
├── models/         # SQLAlchemy ORM models
├── services/       # Business logic (LLM bots, analyzers)
├── api/
│   ├── routes/    # FastAPI route handlers
│   ├── dependencies.py
│   └── schemas.py # Pydantic models
├── templates/     # Jinja2 HTML templates
├── db/           # Database connection & migrations
├── prompts/      # LLM prompt templates
├── config.py     # Environment configuration
└── main.py       # FastAPI application

tests/
├── contract/     # API contract tests
├── integration/  # End-to-end tests
└── unit/        # Service & model tests

static/
├── css/         # Stylesheets
└── js/          # HTMX and client-side scripts

specs/
└── 001-misconception-dialogue-sim/
    ├── spec.md      # Feature specification
    ├── plan.md      # Implementation plan
    ├── tasks.md     # Task breakdown
    ├── progress.md  # Current progress
    └── ...
```

## Development Commands

```bash
# Setup
uv venv                  # Create virtual environment
source .venv/bin/activate  # Activate (Linux/Mac)
uv pip install -e ".[dev]"  # Install dependencies

# Database
python -m src.db.seed    # Initialize and seed database

# Run application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Testing
pytest                   # Run all tests
pytest tests/unit/       # Run unit tests only
pytest --cov=src         # Run with coverage

# Code quality
black .                  # Format code
ruff check .             # Lint code
ruff check --fix .       # Auto-fix linting issues
```

## Code Style

**Python 3.11+**:
- Black formatter: 80 character line length
- Ruff linter: E, F, I, N, W rules
- Type hints: Use Pydantic models and SQLAlchemy mapped columns
- Async/await: Throughout for database and LLM operations

**File Length**: Maximum 300 lines per file (constitution)
**Line Length**: Maximum 80 characters (constitution)
**TDD Workflow**: Write tests FIRST, then implementation

## Recent Changes

- 2025-11-05: Phase 5 complete - Admin scenario management with CRUD operations, role-based access control
- 2025-11-05: Phase 4 complete - Session analysis with LLM classification, visual analytics, CSV export
- 2025-11-05: Phase 3 complete - MVP dialogue system with three-party conversations
- 2025-11-05: Foundation complete - database, API, templates ready
- 2025-11-05: Added Python 3.11+ (uv package manager) + FastAPI, SQLAlchemy 2.x, Jinja2, HTMX

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
