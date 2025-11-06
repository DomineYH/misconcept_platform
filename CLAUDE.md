# misconcept_platform Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-06

## Implementation Status

**Feature**: 001-misconception-dialogue-sim
**Progress**: 112/112 tasks (100%) ✅ COMPLETE
**Phase**: All Phases Complete

### Completed
- ✅ Phase 1-8: All user stories and production polish complete (112/112 tasks)
- ✅ Phase 8: Polish & Production (13/13 tasks)
  - ✅ Error handling & retry logic (tenacity)
  - ✅ Rate limiting (slowapi: 5-30/min)
  - ✅ SQLite WAL mode for concurrency
  - ✅ Structured JSON logging
  - ✅ CORS & security headers
  - ✅ Health & metrics endpoints
  - ✅ Deployment guide (docs/deployment.md)
  - ✅ Code review & refactoring (admin.py split into 4 files)
  - ✅ README update (comprehensive)
  - ✅ Pre-commit hooks (.pre-commit-config.yaml)
  - ✅ Performance optimization (caching, N+1 fix)
  - ✅ Security hardening (HTTPS, httponly, docs/security.md)
  - ✅ Quickstart validation (quickstart.md reviewed)

**Details**: See `specs/001-misconception-dialogue-sim/STATUS.md`

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

- 2025-11-06: Phase 8 complete (100%) - All production polish tasks finished
  - T109: Quickstart validation (quickstart.md reviewed)
  - T110: Pre-commit hooks (.pre-commit-config.yaml)
  - T111: Performance optimization (prompt caching, N+1 query fix)
  - T112: Security hardening (HTTPS, httponly, docs/security.md)
- 2025-11-06: Phase 7 complete - Admin session logs with filtering, CSV export, statistics
- 2025-11-05: Phase 3-6 complete - Full MVP with analysis, admin, framework configuration

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
