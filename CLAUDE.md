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
- OpenAI SDK (LLM integration via Responses API)
  - **Primary Models** (권장): GPT-5, GPT-5.1
  - **Fallback Models** (지원): GPT-4 Turbo
  - Temperature auto-handling for GPT-5/5.1 (fixed at 1.0)
  - All services use Responses API (max_output_tokens parameter)

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

## Development Environment

**필수**: 이 프로젝트는 반드시 `uv` 환경에서 작업합니다.
- 모든 패키지 설치는 `uv pip install`로 수행
- 가상환경 생성은 `uv venv`로 수행
- pip/conda/poetry 등 다른 패키지 매니저 사용 금지

## Development Commands

```bash
# Setup (uv 필수)
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

## Schema Migration Best Practices

**Database migrations are critical**. Follow these guidelines to
prevent schema-code drift and ensure system integrity.

### Required Steps Before Any Migration

1. **ORM Model Diff Analysis**
   - Review all changes in `src/models/*.py`
   - Document added/removed/modified columns

2. **Codebase Reference Search**
   - Search for ALL references to affected columns
   - Use `rg -n "column_name" src/ tests/ templates/`
   - Document impact in affected files

3. **Three-Way Synchronization**
   - Update ORM models (`src/models/`)
   - Write migration SQL (`src/db/migrations/NNN_name.sql`)
   - Update init schema (`src/db/init_schema.py`)

4. **Local Testing**
   - Backup database before migration
   - Run migration SQL
   - Verify schema with `PRAGMA table_info(table_name)`
   - Run all tests: `pytest tests/ -v`

**Detailed Checklist**: See `src/db/migrations/README.md` for
complete 8-step process with commands and verification steps.

## Preventing Schema-Code Drift

Three automated tools prevent migration incidents:

### 1. Contract Tests (Automated Validation)
**File**: `tests/contract/test_schema_integrity.py`

Automatically validates:
- All ORM columns exist in database
- Column types match between ORM and database
- Critical scenario override columns present

**Usage**:
```bash
# Run schema integrity tests
pytest tests/contract/test_schema_integrity.py -v

# Include in CI/CD pipeline
pytest tests/contract/ -v
```

**When**: Run after every migration and in CI/CD pipeline

### 2. Verification Script
**File**: `src/db/migrations/verify_migration.sh`

Comprehensive migration verification:
- Database schema inspection
- ORM model loading test
- Data integrity checks
- Record count validation

**Usage**:
```bash
# Verify migration after applying
./src/db/migrations/verify_migration.sh

# Check specific table
sqlite3 dialogue_sim.db "PRAGMA table_info(scenario);"
```

**When**: Immediately after applying migration

### 3. CI/CD Integration (Recommended)
Add to your CI pipeline:

```yaml
# .github/workflows/test.yml example
- name: Schema Integrity Check
  run: |
    pytest tests/contract/test_schema_integrity.py -v
    ./src/db/migrations/verify_migration.sh
```

**Benefit**: Catch schema drift before production deployment

## Incident Post-Mortem: Migration 003

**Date**: 2025-11-17
**Severity**: High (Production API 500 errors)

### What Happened
Migration 003 removed `chatbot_config` table but accidentally
dropped 4 scenario override columns during table recreation:
- `chat_model` (String)
- `chat_temperature` (Float)
- `tutor_enabled` (Boolean)
- `tutor_intervention_threshold` (Integer)

**Impact**:
- `AttributeError` on ORM model load
- API 500 errors on scenario endpoints
- Scenario-specific chatbot settings broken

### Root Cause
1. ORM models kept columns, but migration SQL omitted them
2. No codebase reference search performed
3. `init_schema.py` synchronization not verified
4. Insufficient testing before deployment

### Resolution
**Migration 006** restored missing columns using table
recreation pattern with data preservation.

**Recovery Time**: ~2 hours (detection + fix + testing)

### Prevention Measures Implemented

**Phase 6 Three-Layer Safety System**:

1. **Documentation** (`src/db/migrations/README.md`)
   - 8-step migration process
   - Mandatory checklist for authors and reviewers
   - SQLite-specific constraints guide

2. **Automated Testing** (`tests/contract/test_schema_integrity.py`)
   - ORM-database column validation
   - Type matching verification
   - Critical column existence checks

3. **Verification Script** (`src/db/migrations/verify_migration.sh`)
   - Post-migration schema inspection
   - Data integrity validation
   - Quick sanity checks

**Key Lesson**: Manual checklists fail. Automation prevents
regression. All three layers must be used for every migration.

## Recent Changes

- 2025-11-18: Analyzer Responses API Migration (Phase 1.5)
  - Migrated analyzer.py from Chat Completions to Responses API
  - Updated 7 unit tests to use Responses API mocks
  - All services now unified on Responses API
  - System-wide GPT-5 support enabled (ANALYSIS_MODEL=gpt-5 safe)
  - 100% test coverage maintained (7/7 tests passing)
- 2025-11-18: Documentation Accuracy Update (Phase 2)
  - Updated CLAUDE.md model support (Primary: GPT-5/5.1)
  - All 4 services confirmed using Responses API
  - Deployment blocker eliminated (analyzer compatibility)
  - System integrity: 100% API consistency achieved
- 2025-11-17: GPT-5.1 Model Support Enabled
  - Added gpt-5.1-chat-latest and gpt-5.1 model support
  - Code already compatible (temperature auto-handling exists)
  - Updated .env.example, src/config.py, test parametrization
  - Created comprehensive migration guide (docs/gpt-5-migration.md)
  - Zero code changes required - defensive programming FTW!
- 2025-11-17: Schema Migration Regression Fix (Phase 1-6 complete)
  - Fixed Migration 003 regression via Migration 006
  - Restored 4 scenario override columns
  - Implemented 3-layer prevention system:
    * Migration checklist (README.md)
    * Schema integrity tests (contract tests)
    * Verification script (verify_migration.sh)
  - Updated documentation with incident post-mortem
- 2025-11-06: Phase 8 complete (100%) - All production polish tasks
  - T109: Quickstart validation (quickstart.md reviewed)
  - T110: Pre-commit hooks (.pre-commit-config.yaml)
  - T111: Performance optimization (prompt caching, N+1 query fix)
  - T112: Security hardening (HTTPS, httponly, docs/security.md)
- 2025-11-06: Phase 7 complete - Admin session logs with filtering,
  CSV export, statistics
- 2025-11-05: Phase 3-6 complete - Full MVP with analysis, admin,
  framework configuration

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
