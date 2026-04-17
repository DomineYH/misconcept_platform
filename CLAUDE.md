# gstack + Superpowers Operating Rules

Aligned with the official repositories: `garrytan/gstack` + `obra/superpowers`.

## gstack

- Use gstack `/browse` family for web navigation, real browser interaction, visual QA, and authentication flow verification.
- Do not use `mcp__claude-in-chrome__*` tools.
- If gstack was installed with `--prefix`, use prefixed names consistently (`/gstack-review`, `/gstack-qa`, etc.).
- Available gstack commands:
  `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`
- If gstack commands are not visible or not working, recover in this order:
  - Repo-local install: `cd .claude/skills/gstack && ./setup`
  - Global install: `cd ~/.claude/skills/gstack && ./setup`

## Purpose of This Document

- `CLAUDE.md` holds only global routing rules, paths, ownership, and safety guardrails.
- Do not accumulate lengthy design descriptions, meeting notes, changelogs, strategy bodies, or implementation plans in this file.
- When the session changes, do not assume shared memory — re-read the canonical documents.
- For Superpowers, refer to skill names (`brainstorming`, `writing-plans`, `subagent-driven-development`, etc.) rather than legacy slash commands.

## Canonical Artifacts (Source of Truth)

- `DESIGN.md`
  - Root design system, UI rules, tone, and interaction standards.
  - Reference document for gstack design-related skills (`/design-consultation`, `/design-shotgun`, `/design-review`).
  - This is distinct from the product strategy design doc created by `/office-hours`. `DESIGN.md` covers the visual/UX system; the `/office-hours` design doc covers product direction.

- `docs/gstack/strategy/YYYY-MM-DD-<topic>.md`
  - Stores conclusions from gstack strategy skills (`/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/autoplan`).
  - May be skipped if running consecutively within the same session. Must be saved when the session changes.
  - When multiple reviews are run on the same topic, append sections to the same file.

- `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - Approved feature spec produced by Superpowers `brainstorming`.

- `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
  - Execution plan produced by Superpowers `writing-plans`.

- `docs/ai-handoffs/YYYY-MM-DD-<topic>.md`
  - Created when a session transition or tool handoff is needed.
  - Contains pointers only, not duplicated body text.
  - When handing off from gstack strategy to Superpowers implementation across sessions, the strategy document path must be included.

- `.context/plans/*`
  - No longer used as canonical source of truth.
  - Used only as a temporary handoff/index when legacy flows depend heavily on it.

### Artifact Creation Notification

Whenever a canonical artifact file is newly created or updated, the user must be notified.
- The notification must include the file path, whether it was created or updated, and a 1–2 line summary of the change.
- If multiple files were created at once, notify as a single grouped list.
- Do not silently create or overwrite canonical artifacts without notification.

## Pre-Task Reading Order

- Always: `CLAUDE.md`
- If UI/UX is involved: `DESIGN.md`
- If strategy decisions preceded this work: latest document in `docs/gstack/strategy/`
- If extending/modifying an existing feature: latest spec + plan
- If reviewing/QA/deploying: strategy document + spec + plan + diff + `DESIGN.md`
- If debugging: reproduction info, failing tests, related spec/plan

## Role Separation

### gstack Owns

- Product direction redefinition, scope challenges, priority decisions
- Architecture / design / QA / security / performance / deployment decisions
- Real-browser-based QA and visual audits
- Release and documentation synchronization
- Engineering retrospectives

### Superpowers Owns

- Feature spec authoring and approval flow
- Worktree creation and clean test baseline setup
- Detailed execution plan authoring
- TDD implementation, code review loops, verification, systematic debugging

## Default Routing

- If the problem definition is unclear, or user value, priorities, or UX direction are central, start with gstack.
- If requirements are already clear and the feature is ready to code, start with Superpowers.
- Do not force both a gstack strategy phase and Superpowers brainstorming on every feature.
- Do not assign two branch finalization owners to the same change.

## Recommended Workflows

### 1) New Feature / Unclear Scope

1. gstack: `/office-hours` or `/autoplan`
2. As needed — gstack: `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`
3. If no design system exists or a major UI change is involved — gstack: `/design-consultation` or `/design-shotgun`
4. **If the session changes**, save strategy conclusions to `docs/gstack/strategy/YYYY-MM-DD-<topic>.md`. May be skipped if continuing in the same session.
5. Subsequent sessions re-read the updated `DESIGN.md`, `CLAUDE.md`, and strategy documents.
6. Superpowers: `brainstorming`
7. Superpowers: `using-git-worktrees`
8. Superpowers: `writing-plans`
9. Superpowers: `subagent-driven-development`
10. Superpowers: `requesting-code-review` / `receiving-code-review`
11. Superpowers: `verification-before-completion`
12. gstack: `/review`, `/qa` or `/qa-only`, `/design-review`, `/cso`, `/benchmark` — only as needed
13. gstack: `/ship` → `/land-and-deploy` → `/canary`
14. Optional: gstack `/retro` (post-deploy weekly retrospective or per-project retrospective)

### 2) Clear Requirements / Refactor / Small Improvement

1. Superpowers: `brainstorming`
2. Superpowers: `using-git-worktrees`
3. Superpowers: `writing-plans` (do not skip even for small tasks if the verification path is unclear)
4. Superpowers: `subagent-driven-development`
5. Enforce `test-driven-development` during implementation.
6. Superpowers: `requesting-code-review`
7. Superpowers: `verification-before-completion`
8. gstack: `/review`
9. As needed — gstack: `/design-review`, `/qa`, `/cso`, `/benchmark`
10. gstack: `/ship`

### 3) Bug Fix / Regression / Production Issue

1. For live issues, hard-to-reproduce problems, or browser issues — start with gstack `/investigate`
2. For in-repo root cause analysis — Superpowers `systematic-debugging`
3. Fix using `test-driven-development`, starting with a failing test
4. Before declaring completion — `verification-before-completion`
5. As needed — `/qa`, `/review`, `/cso`

## Session Transition Rules

- **When running gstack → Superpowers consecutively in the same session**, the strategy conclusions remain in the context window, so separate file saving is not required.
- **When the session changes** (new session, different terminal, Conductor parallel session, etc.), one of the following must be performed:
  - Save strategy conclusions to `docs/gstack/strategy/`
  - Create a handoff document in `docs/ai-handoffs/` (pointers only)
- A Superpowers session must read the latest document in `docs/gstack/strategy/` at startup and verify alignment before entering `brainstorming`.
- A gstack review/QA session must read the strategy document + spec + plan at startup and review plan-vs-implementation alignment alongside the code review.

## Worktree Rules

- Default worktree root is `.worktrees/`.
- `.worktrees/` must remain gitignored.
- If the worktree path is ambiguous, follow the order: `existing > CLAUDE.md > ask`.
- Implementation is done in a worktree by default.
- Do not implement directly on `main`/`master`. Only exception: explicit user approval.
- After creating a worktree, verify project setup and a clean test baseline first.

### Worktree Preference

```md
Use `.worktrees/` for project-local git worktrees.
Assume `.worktrees/` is gitignored.
Do not start implementation directly on main/master without explicit approval.
```

## Implementation Rules

- `test-driven-development` is the default principle.
- Do not write production code without a failing test first.
- In environments that support subagents (e.g., Claude Code), use `subagent-driven-development` as the default executor.
- Use `executing-plans` only when subagents are unavailable, when plan execution is needed in a separate session, or when the user explicitly requests that flow.
- Use `dispatching-parallel-agents` only for independent tasks with no shared state and no sequential dependencies.
- Do not split the same feature implementation across multiple parallel implementers for simultaneous editing.
- Insert `requesting-code-review` between significant steps, and respond to feedback using the `receiving-code-review` flow.
- Before declaring completion, always leave fresh evidence via `verification-before-completion`.

## Review / QA / Deploy Rules

- Product direction review: `/plan-ceo-review`
- Architecture / edge cases / test strategy review: `/plan-eng-review`
- Pre-implementation UX/visual quality review: `/plan-design-review`
- Post-implementation UI audit with fixes: `/design-review`
- Overall code/quality review: `/review`
- Browser-based testing and regression verification: `/qa`
- Report-only mode: `/qa-only`
- Security audit: `/cso`
- Performance baseline/comparison: `/benchmark`
- Post-deploy documentation sync: `/document-release` (auto-invoked by `/ship`, so separate execution is optional)

### Branch Finalization Owner

- The default owner is gstack `/ship`.
- Use `finishing-a-development-branch` only when:
  - A local merge / keep / discard decision is needed first.
  - The user explicitly wants the Superpowers finalization flow instead of the gstack release flow.
- Do not use both `finishing-a-development-branch` and `/ship` as PR owners on the same change.

## Browser Rules

- Use gstack `/browse` for web navigation, real page interaction, screenshots, DOM inspection, and post-authentication scenario verification.
- Use `/connect-chrome` when headed real Chrome control is needed.
- Use `/setup-browser-cookies` to import cookies from a local browser.
- If the agent is blocked by CAPTCHA/MFA: `$B handoff` → user resolves → `$B resume`.

## Documentation Rules

- Keep `DESIGN.md` at the project root. UI-related gstack reviews are calibrated against this file.
- Default path for gstack strategy conclusions: `docs/gstack/strategy/`.
- Default paths for Superpowers specs/plans: `docs/superpowers/specs/`, `docs/superpowers/plans/`.
- Do not customize these paths without a specific reason.
- Summarize long-term strategic decisions in handoff documents or in the decision section of the relevant spec.
- Do not let `CLAUDE.md` grow into a meeting log.
- Use `/document-release` when post-deploy documentation sync is needed.

## Optional Handoff Template

```md
# AI Handoff — YYYY-MM-DD
- Design authority: DESIGN.md
- Strategy: docs/gstack/strategy/YYYY-MM-DD-<topic>.md
- Current spec: docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
- Current plan: docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md
- Worktree: .worktrees/<branch-name>
- Current branch: <branch-name>
- Next step: <one specific next action>
```

## Efficiency Rules

- Do not run `/office-hours` and `brainstorming` back-to-back on every task.
- Scope reviews/QA narrowly. Do not automatically run every reviewer.
- Do not duplicate content in `CLAUDE.md` that belongs in `DESIGN.md`, specs, or plans.
- Do not parallelize implementation tasks that are not independent.
- Assign release decisions and PR creation responsibility to one tool only.
- Do not force intermediate file saves for consecutive runs within the same session.

## Safety Guardrails

- Before destructive git / DB / filesystem commands: `/careful`
- For production work or risky refactors: `/guard`
- To protect a specific area during investigation: `/freeze`
- When investigation is complete: `/unfreeze`

## Auxiliary Skills

- Superpowers: `using-superpowers`, `writing-skills`
- gstack: `/setup-deploy`, `/gstack-upgrade`

## Maintenance Notes

- When running gstack and Superpowers together, prefer `./setup --prefix` for gstack to avoid command collisions.
- If shorter commands are more important, `./setup --no-prefix` is available, but accept the risk of collision with other skill packs.
- Update Superpowers: `/plugin update superpowers`
- Update gstack: `/gstack-upgrade` or use the configured auto-upgrade flow.
- On Windows, `/browse` family may require both Bun and Node.js.

## Quick Decision Table

- Product / priorities / design direction is the problem → gstack
- Implementation planning and TDD coding is the problem → Superpowers
- Need to see if it breaks in a real browser → gstack `/browse` / `/qa`
- Need systematic root cause analysis → Superpowers `systematic-debugging`
- Want to wrap up PR / deploy / doc sync in one go → gstack `/ship`
- Want to review productivity/quality trends after deploy → gstack `/retro`

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

# gstack + Superpowers Operating Rules

Aligned with the official repositories: `garrytan/gstack` + `obra/superpowers`.

## gstack

- Use gstack `/browse` family for web navigation, real browser interaction, visual QA, and authentication flow verification.
- Do not use `mcp__claude-in-chrome__*` tools.
- If gstack was installed with `--prefix`, use prefixed names consistently (`/gstack-review`, `/gstack-qa`, etc.).
- Available gstack commands:
  `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`
- If gstack commands are not visible or not working, recover in this order:
  - Repo-local install: `cd .claude/skills/gstack && ./setup`
  - Global install: `cd ~/.claude/skills/gstack && ./setup`

## Purpose of This Document

- `CLAUDE.md` holds only global routing rules, paths, ownership, and safety guardrails.
- Do not accumulate lengthy design descriptions, meeting notes, changelogs, strategy bodies, or implementation plans in this file.
- When the session changes, do not assume shared memory — re-read the canonical documents.
- For Superpowers, refer to skill names (`brainstorming`, `writing-plans`, `subagent-driven-development`, etc.) rather than legacy slash commands.

## Canonical Artifacts (Source of Truth)

- `DESIGN.md`
  - Root design system, UI rules, tone, and interaction standards.
  - Reference document for gstack design-related skills (`/design-consultation`, `/design-shotgun`, `/design-review`).
  - This is distinct from the product strategy design doc created by `/office-hours`. `DESIGN.md` covers the visual/UX system; the `/office-hours` design doc covers product direction.

- `docs/gstack/strategy/YYYY-MM-DD-<topic>.md`
  - Stores conclusions from gstack strategy skills (`/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/autoplan`).
  - May be skipped if running consecutively within the same session. Must be saved when the session changes.
  - When multiple reviews are run on the same topic, append sections to the same file.

- `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - Approved feature spec produced by Superpowers `brainstorming`.

- `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
  - Execution plan produced by Superpowers `writing-plans`.

- `docs/ai-handoffs/YYYY-MM-DD-<topic>.md`
  - Created when a session transition or tool handoff is needed.
  - Contains pointers only, not duplicated body text.
  - When handing off from gstack strategy to Superpowers implementation across sessions, the strategy document path must be included.

- `.context/plans/*`
  - No longer used as canonical source of truth.
  - Used only as a temporary handoff/index when legacy flows depend heavily on it.

### Artifact Creation Notification

Whenever a canonical artifact file is newly created or updated, the user must be notified.
- The notification must include the file path, whether it was created or updated, and a 1–2 line summary of the change.
- If multiple files were created at once, notify as a single grouped list.
- Do not silently create or overwrite canonical artifacts without notification.

## Pre-Task Reading Order

- Always: `CLAUDE.md`
- If UI/UX is involved: `DESIGN.md`
- If strategy decisions preceded this work: latest document in `docs/gstack/strategy/`
- If extending/modifying an existing feature: latest spec + plan
- If reviewing/QA/deploying: strategy document + spec + plan + diff + `DESIGN.md`
- If debugging: reproduction info, failing tests, related spec/plan

## Role Separation

### gstack Owns

- Product direction redefinition, scope challenges, priority decisions
- Architecture / design / QA / security / performance / deployment decisions
- Real-browser-based QA and visual audits
- Release and documentation synchronization
- Engineering retrospectives

### Superpowers Owns

- Feature spec authoring and approval flow
- Worktree creation and clean test baseline setup
- Detailed execution plan authoring
- TDD implementation, code review loops, verification, systematic debugging

## Default Routing

- If the problem definition is unclear, or user value, priorities, or UX direction are central, start with gstack.
- If requirements are already clear and the feature is ready to code, start with Superpowers.
- Do not force both a gstack strategy phase and Superpowers brainstorming on every feature.
- Do not assign two branch finalization owners to the same change.

## Recommended Workflows

### 1) New Feature / Unclear Scope

1. gstack: `/office-hours` or `/autoplan`
2. As needed — gstack: `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`
3. If no design system exists or a major UI change is involved — gstack: `/design-consultation` or `/design-shotgun`
4. **If the session changes**, save strategy conclusions to `docs/gstack/strategy/YYYY-MM-DD-<topic>.md`. May be skipped if continuing in the same session.
5. Subsequent sessions re-read the updated `DESIGN.md`, `CLAUDE.md`, and strategy documents.
6. Superpowers: `brainstorming`
7. Superpowers: `using-git-worktrees`
8. Superpowers: `writing-plans`
9. Superpowers: `subagent-driven-development`
10. Superpowers: `requesting-code-review` / `receiving-code-review`
11. Superpowers: `verification-before-completion`
12. gstack: `/review`, `/qa` or `/qa-only`, `/design-review`, `/cso`, `/benchmark` — only as needed
13. gstack: `/ship` → `/land-and-deploy` → `/canary`
14. Optional: gstack `/retro` (post-deploy weekly retrospective or per-project retrospective)

### 2) Clear Requirements / Refactor / Small Improvement

1. Superpowers: `brainstorming`
2. Superpowers: `using-git-worktrees`
3. Superpowers: `writing-plans` (do not skip even for small tasks if the verification path is unclear)
4. Superpowers: `subagent-driven-development`
5. Enforce `test-driven-development` during implementation.
6. Superpowers: `requesting-code-review`
7. Superpowers: `verification-before-completion`
8. gstack: `/review`
9. As needed — gstack: `/design-review`, `/qa`, `/cso`, `/benchmark`
10. gstack: `/ship`

### 3) Bug Fix / Regression / Production Issue

1. For live issues, hard-to-reproduce problems, or browser issues — start with gstack `/investigate`
2. For in-repo root cause analysis — Superpowers `systematic-debugging`
3. Fix using `test-driven-development`, starting with a failing test
4. Before declaring completion — `verification-before-completion`
5. As needed — `/qa`, `/review`, `/cso`

## Session Transition Rules

- **When running gstack → Superpowers consecutively in the same session**, the strategy conclusions remain in the context window, so separate file saving is not required.
- **When the session changes** (new session, different terminal, Conductor parallel session, etc.), one of the following must be performed:
  - Save strategy conclusions to `docs/gstack/strategy/`
  - Create a handoff document in `docs/ai-handoffs/` (pointers only)
- A Superpowers session must read the latest document in `docs/gstack/strategy/` at startup and verify alignment before entering `brainstorming`.
- A gstack review/QA session must read the strategy document + spec + plan at startup and review plan-vs-implementation alignment alongside the code review.

## Worktree Rules

- Default worktree root is `.worktrees/`.
- `.worktrees/` must remain gitignored.
- If the worktree path is ambiguous, follow the order: `existing > CLAUDE.md > ask`.
- Implementation is done in a worktree by default.
- Do not implement directly on `main`/`master`. Only exception: explicit user approval.
- After creating a worktree, verify project setup and a clean test baseline first.

### Worktree Preference

```md
Use `.worktrees/` for project-local git worktrees.
Assume `.worktrees/` is gitignored.
Do not start implementation directly on main/master without explicit approval.
```

## Implementation Rules

- `test-driven-development` is the default principle.
- Do not write production code without a failing test first.
- In environments that support subagents (e.g., Claude Code), use `subagent-driven-development` as the default executor.
- Use `executing-plans` only when subagents are unavailable, when plan execution is needed in a separate session, or when the user explicitly requests that flow.
- Use `dispatching-parallel-agents` only for independent tasks with no shared state and no sequential dependencies.
- Do not split the same feature implementation across multiple parallel implementers for simultaneous editing.
- Insert `requesting-code-review` between significant steps, and respond to feedback using the `receiving-code-review` flow.
- Before declaring completion, always leave fresh evidence via `verification-before-completion`.

## Review / QA / Deploy Rules

- Product direction review: `/plan-ceo-review`
- Architecture / edge cases / test strategy review: `/plan-eng-review`
- Pre-implementation UX/visual quality review: `/plan-design-review`
- Post-implementation UI audit with fixes: `/design-review`
- Overall code/quality review: `/review`
- Browser-based testing and regression verification: `/qa`
- Report-only mode: `/qa-only`
- Security audit: `/cso`
- Performance baseline/comparison: `/benchmark`
- Post-deploy documentation sync: `/document-release` (auto-invoked by `/ship`, so separate execution is optional)

### Branch Finalization Owner

- The default owner is gstack `/ship`.
- Use `finishing-a-development-branch` only when:
  - A local merge / keep / discard decision is needed first.
  - The user explicitly wants the Superpowers finalization flow instead of the gstack release flow.
- Do not use both `finishing-a-development-branch` and `/ship` as PR owners on the same change.

## Browser Rules

- Use gstack `/browse` for web navigation, real page interaction, screenshots, DOM inspection, and post-authentication scenario verification.
- Use `/connect-chrome` when headed real Chrome control is needed.
- Use `/setup-browser-cookies` to import cookies from a local browser.
- If the agent is blocked by CAPTCHA/MFA: `$B handoff` → user resolves → `$B resume`.

## Documentation Rules

- Keep `DESIGN.md` at the project root. UI-related gstack reviews are calibrated against this file.
- Default path for gstack strategy conclusions: `docs/gstack/strategy/`.
- Default paths for Superpowers specs/plans: `docs/superpowers/specs/`, `docs/superpowers/plans/`.
- Do not customize these paths without a specific reason.
- Summarize long-term strategic decisions in handoff documents or in the decision section of the relevant spec.
- Do not let `CLAUDE.md` grow into a meeting log.
- Use `/document-release` when post-deploy documentation sync is needed.

## Optional Handoff Template

```md
# AI Handoff — YYYY-MM-DD
- Design authority: DESIGN.md
- Strategy: docs/gstack/strategy/YYYY-MM-DD-<topic>.md
- Current spec: docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
- Current plan: docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md
- Worktree: .worktrees/<branch-name>
- Current branch: <branch-name>
- Next step: <one specific next action>
```

## Efficiency Rules

- Do not run `/office-hours` and `brainstorming` back-to-back on every task.
- Scope reviews/QA narrowly. Do not automatically run every reviewer.
- Do not duplicate content in `CLAUDE.md` that belongs in `DESIGN.md`, specs, or plans.
- Do not parallelize implementation tasks that are not independent.
- Assign release decisions and PR creation responsibility to one tool only.
- Do not force intermediate file saves for consecutive runs within the same session.

## Safety Guardrails

- Before destructive git / DB / filesystem commands: `/careful`
- For production work or risky refactors: `/guard`
- To protect a specific area during investigation: `/freeze`
- When investigation is complete: `/unfreeze`

## Auxiliary Skills

- Superpowers: `using-superpowers`, `writing-skills`
- gstack: `/setup-deploy`, `/gstack-upgrade`

## Maintenance Notes

- When running gstack and Superpowers together, prefer `./setup --prefix` for gstack to avoid command collisions.
- If shorter commands are more important, `./setup --no-prefix` is available, but accept the risk of collision with other skill packs.
- Update Superpowers: `/plugin update superpowers`
- Update gstack: `/gstack-upgrade` or use the configured auto-upgrade flow.
- On Windows, `/browse` family may require both Bun and Node.js.

## Quick Decision Table

- Product / priorities / design direction is the problem → gstack
- Implementation planning and TDD coding is the problem → Superpowers
- Need to see if it breaks in a real browser → gstack `/browse` / `/qa`
- Need systematic root cause analysis → Superpowers `systematic-debugging`
- Want to wrap up PR / deploy / doc sync in one go → gstack `/ship`
- Want to review productivity/quality trends after deploy → gstack `/retro`

## Post-Task Recommendations & Optimized Prompts

After completing any task or workflow step, the assistant **must** present recommended next steps along with ready-to-use optimized prompts. This eliminates guesswork and lets the user proceed immediately.

### Recommendation Rules

- Present 2–3 recommendations ranked by priority (most impactful first).
- Recommendations must be context-aware: consider the current workflow stage, what was just completed, and remaining goals.
- Do not recommend steps already completed in the current session.
- Each recommendation includes:
  - **What**: Brief description of the recommended next task
  - **Why**: Why this is the logical next step in the current context
  - **Prompt**: An optimized, copy-paste-ready prompt the user can execute directly
- Prompts must reference concrete artifacts (file paths, branch names, spec/plan paths) produced during the session.

### Output Format

```
### Recommended Next Steps

1. **[Task Name]** — [Brief reason why this is recommended now]
   > Prompt:
   > ```
   > [Optimized prompt for this task]
   > ```

2. **[Task Name]** — [Brief reason]
   > Prompt:
   > ```
   > [Optimized prompt]
   > ```

3. **[Task Name]** (optional) — [Brief reason]
   > Prompt:
   > ```
   > [Optimized prompt]
   > ```
```

### Workflow-Aware Prompt Templates

The recommended prompts vary by what was just completed:

| Just Completed | Recommended Next | Prompt Template |
|---|---|---|
| `brainstorming` | `writing-plans` | `Write an execution plan based on the approved spec at docs/superpowers/specs/<spec-path>. Include test strategy and verification steps.` |
| `writing-plans` | `subagent-driven-development` | `Execute the plan at docs/superpowers/plans/<plan-path>. Use TDD — write failing tests first, then implement.` |
| Implementation step | `requesting-code-review` | `Review the changes on branch <branch-name>. Focus on plan alignment, test coverage, and edge cases.` |
| `requesting-code-review` | `verification-before-completion` | `Run full verification on branch <branch-name>: tests, type checks, lint. Confirm all checks pass before proceeding.` |
| `verification-before-completion` | gstack `/ship` or `finishing-a-development-branch` | `Ship branch <branch-name>. Run tests, review diff, bump version, create PR against main.` |
| `/office-hours` or `/autoplan` | `brainstorming` or plan review | `Start brainstorming based on the strategy document at docs/gstack/strategy/<strategy-path>. Validate alignment before proceeding.` |
| `/review` | `/qa` or `/ship` | `Run QA on <url> — test the golden path and edge cases identified in the review.` |
| `/qa` (bugs found) | Bug fix workflow | `Fix the bugs found in QA. Start with a failing test for each issue, then implement fixes using TDD.` |
| `/qa` (all clear) | `/ship` | `Ship branch <branch-name>. QA passed — proceed with version bump and PR creation.` |
| Bug fix | `verification-before-completion` | `Verify the fix on branch <branch-name>. Run the regression test suite and confirm the original issue is resolved.` |
| `/ship` | `/canary` or `/retro` | `Monitor the deploy with canary checks on <production-url>. Watch for console errors and performance regressions.` |
| `systematic-debugging` | TDD fix | `Apply the root cause fix identified in debugging. Write a failing test that reproduces the bug first, then implement the fix.` |

### When to Skip Recommendations

- When the user has explicitly stated their next action.
- When the session is ending and the user has asked for a handoff document instead.
- Inside subagent execution — only the orchestrator presents recommendations, not individual subagents.
