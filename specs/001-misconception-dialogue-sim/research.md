# Research: Misconception Dialogue Simulator

**Feature**: 001-misconception-dialogue-sim
**Date**: 2025-11-05
**Status**: Phase 0 Complete

## Research Objectives

1. Validate technology stack choices for educational dialogue simulator
2. Identify best practices for LLM integration (dual-model architecture)
3. Determine optimal state management for three-party dialogue
4. Research cookie-based authentication security for minimal-data context
5. Evaluate HTMX patterns for real-time UI updates without WebSocket

## Technology Stack Validation

### Python 3.11+ with uv Package Manager

**Decision**: Use Python 3.11+ with uv for fast dependency resolution

**Rationale**:
- Python 3.11+ provides significant performance improvements (10-60%
  faster than 3.10)
- `uv` package manager offers 10-100x faster dependency resolution than
  pip
- Excellent ecosystem for LLM integration (OpenAI SDK, LangChain)
- Strong typing support with Pydantic for data validation
- Mature async/await support for concurrent LLM calls

**Alternatives Considered**:
- **Node.js + TypeScript**: Rejected due to less mature LLM ecosystem,
  heavier async complexity for educational use case
- **Python 3.10**: Rejected due to missing performance improvements and
  pattern matching features

### FastAPI with Server-Side Rendering

**Decision**: FastAPI + Jinja2 templates for SSR, HTMX for interactivity

**Rationale**:
- FastAPI provides automatic OpenAPI documentation (critical for contract
  tests)
- Jinja2 SSR eliminates complex frontend build pipeline
- HTMX enables partial page updates without JavaScript framework overhead
- Native async support for concurrent LLM API calls
- Excellent developer experience with auto-reload and type hints

**Alternatives Considered**:
- **Flask + React SPA**: Rejected due to added complexity of separate
  frontend build, CORS handling, and state synchronization
- **Django**: Rejected due to heavier ORM (unnecessary for SQLite), slower
  async adoption, more boilerplate

### SQLite3 with SQLAlchemy 2.x

**Decision**: SQLite3 for simplicity, SQLAlchemy 2.x ORM for type safety

**Rationale**:
- Single-file database simplifies deployment (no separate DB server)
- Sufficient for 100 concurrent sessions (read-heavy workload)
- SQLAlchemy 2.x provides modern async support and Pydantic integration
- Easy migration path to PostgreSQL if scaling beyond 200 users

**Alternatives Considered**:
- **PostgreSQL**: Rejected for initial version due to deployment
  complexity, overkill for expected scale
- **Raw SQL**: Rejected due to lack of type safety, migration management,
  and increased boilerplate

### HTMX for Partial Updates

**Decision**: HTMX for real-time message updates, fallback to polling

**Rationale**:
- HTMX enables server-driven UI updates without WebSocket complexity
- Simpler error handling and reconnection logic than WebSockets
- Lower latency tolerance (2s) makes polling acceptable for MVP
- Easy migration path to WebSockets if real-time becomes critical

**Best Practices**:
- Use `hx-trigger="every 2s"` for message polling during active dialogue
- Server responds with HTML fragments (Jinja partials) for HTMX swap
- Implement `hx-swap="beforeend"` for message append pattern
- Add loading indicators with `hx-indicator` for user feedback

**Alternatives Considered**:
- **WebSocket (Socket.IO)**: Rejected for MVP due to added complexity,
  connection management, and unnecessary for 2s latency requirement
- **Server-Sent Events (SSE)**: Rejected due to limited browser support
  for bidirectional communication

## LLM Integration Architecture

### Dual-Model Design

**Decision**: Separate LLM instances for dialogue and analysis

**Rationale**:
- **Dialogue LLM** (Student + Tutor): Requires conversational context,
  state management, and role-playing consistency
- **Analysis LLM**: Stateless question classification, batch-friendly,
  can use smaller/faster model
- Separation prevents context pollution (analysis reasoning leaking into
  dialogue)
- Enables independent scaling and cost optimization

**Implementation Pattern**:
```python
# Dialogue LLM: OpenAI GPT-4 (or GPT-5 when available)
chat_model = "gpt-4-turbo"  # Conversation quality critical

# Analysis LLM: OpenAI GPT-3.5-turbo (sufficient for classification)
analysis_model = "gpt-3.5-turbo"  # Cost-effective, fast

# Student bot maintains conversation history
student_bot = ChatOpenAI(
    model=chat_model,
    system_prompt=load_scenario_prompt(scenario_id)
)

# Analyzer is stateless, single-turn classification
analyzer = ChatOpenAI(
    model=analysis_model,
    system_prompt=load_analysis_prompt(framework_id)
)
```

**Alternatives Considered**:
- **Single model for both**: Rejected due to context pollution risk and
  inflexible cost optimization
- **Local LLM (Llama2)**: Rejected due to educational use case requiring
  high-quality dialogue, deployment complexity

### Prompt Engineering Strategy

**Decision**: Template-based prompts with scenario-specific variables

**Research Findings**:
- System prompts should define role, constraints, and output format
- Few-shot examples critical for consistent pedagogical move
  classification
- Structured output (JSON schema) reduces parsing errors
- Temperature=0.7 for dialogue (creative), 0.2 for analysis (consistent)

**Prompt Structure**:
```text
# student_system.txt (template)
You are a {grade} student with the following misconception about
{topic}:

{misconception_description}

Problem context: {problem}

Your behavior:
- Initially exhibit the misconception consistently
- Respond to conceptual questions with partial understanding
- After {threshold} high-leverage questions, demonstrate "aha moment"
- Maintain realistic student language and reasoning

Constraints:
- Do not explain the misconception directly
- Show work/reasoning when asked
- Stay in character
```

## Authentication and Session Management

### Cookie-Based Minimal Auth

**Decision**: Simple cookie-based session with student ID + nickname

**Rationale**:
- Educational context does not require strong authentication (no PII)
- Unique (student_id, nickname) pair provides sufficient identification
- Session cookies enable stateful dialogue tracking
- FastAPI's `SessionMiddleware` provides CSRF protection

**Security Measures**:
- HttpOnly cookies prevent XSS access
- SameSite=Lax prevents CSRF in most cases
- Short session timeout (8 hours) for active sessions
- Optional hash student_id for additional anonymization

**Implementation**:
```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    session_cookie="session_id",
    max_age=28800,  # 8 hours
    same_site="lax",
    https_only=True  # production only
)
```

**Alternatives Considered**:
- **JWT tokens**: Rejected due to unnecessary complexity for server-side
  rendering
- **OAuth2**: Rejected due to overkill for minimal-auth educational tool

## Three-Party Dialogue State Machine

### State Management Pattern

**Decision**: Server-side state machine with database persistence

**Rationale**:
- All dialogue state persisted in `session` and `message` tables
- Server orchestrates turn-taking: teacher → student → tutor (optional)
- Tutor intervention uses rule-based triggers + LLM confidence scoring
- Auto-save every 30s prevents data loss during network interruptions

**State Flow**:
```
1. Teacher submits message via POST /messages
2. Server creates message record (role=teacher)
3. Trigger analysis LLM (async, non-blocking)
4. Student LLM generates response with conversation history
5. Tutor LLM evaluates need for intervention
   - Check: last N turns stagnant? topic drifted?
   - Check: low-leverage question count > threshold?
6. If intervention needed, tutor message inserted
7. HTMX returns HTML fragments for new messages
8. Client polls for updates every 2s during active session
```

**Intervention Triggers**:
- **Stagnation**: Last 5 messages show no conceptual progress
- **Derailment**: Topic similarity score < 0.6 (cosine similarity)
- **Low Leverage**: >3 consecutive directing/recall questions

## CSV Export Format

**Decision**: UTF-8 CSV with anonymized session identifiers

**Research Findings**:
- Include timestamp, role, content, classification, confidence
- One row per message for easy analysis in R/Python
- Anonymize student_id → session-specific hash
- Include session summary (distribution, feedback) as final row

**Format**:
```csv
session_id,scenario_title,student_hash,timestamp,role,content,label,
confidence,feedback
sess_001,Fractions,abc123,2025-11-05T10:15:00,teacher,"Why do you
think...",Pressing,0.89,
sess_001,Fractions,abc123,2025-11-05T10:15:15,student,"Because the
denominator...",,,
sess_001,Fractions,abc123,2025-11-05T10:15:45,tutor,"Consider asking
about...",,,
sess_001,Fractions,abc123,2025-11-05T10:20:00,SUMMARY,,,,"High
leverage: 60%, Session duration: 5min"
```

## Best Practices Summary

### FastAPI Patterns

- Use dependency injection for database sessions and auth
- Separate Pydantic schemas (request/response) from SQLAlchemy models
- Use `APIRouter` to group related endpoints
- Implement `@lru_cache` for expensive prompt template loading

### SQLAlchemy 2.x Patterns

- Use declarative base with `mapped_column` for type hints
- Enable lazy="selectin" for relationships to avoid N+1 queries
- Use `AsyncSession` for concurrent LLM calls
- Implement database connection pooling with `create_async_engine`

### Testing Strategy

- Mock LLM responses with fixture data for deterministic tests
- Use pytest-asyncio for async test support
- Implement database transaction rollback for test isolation
- Contract tests validate OpenAPI schema compliance

### Deployment Considerations

- Use `uvicorn` with `--workers 4` for production
- Set `OPENAI_API_KEY` via environment variable
- Enable SQLite WAL mode for concurrent read performance
- Configure logging with structured JSON for analysis

## Open Questions (Resolved)

1. **Q**: Should we use WebSocket for real-time updates?
   **A**: No, HTMX polling sufficient for 2s latency requirement, simpler
   error handling

2. **Q**: Should we use local LLM for cost savings?
   **A**: No, educational dialogue quality critical, OpenAI provides
   better pedagogical responses

3. **Q**: Should student_id be hashed for privacy?
   **A**: Optional but recommended, use SHA-256 with session-specific
   salt for CSV export

4. **Q**: Should we implement database migrations (Alembic)?
   **A**: Optional for MVP, add if schema evolution becomes frequent,
   SQLite schema changes manageable manually initially

## References

- FastAPI documentation: https://fastapi.tiangolo.com/
- HTMX patterns: https://htmx.org/examples/
- OpenAI best practices: https://platform.openai.com/docs/guides/
  prompt-engineering
- SQLAlchemy 2.x async: https://docs.sqlalchemy.org/en/20/orm/
  extensions/asyncio.html
