# Quickstart: Misconception Dialogue Simulator

**Feature**: 001-misconception-dialogue-sim
**Target Audience**: Developers implementing this feature
**Estimated Reading Time**: 10 minutes

## Prerequisites

- Python 3.11 or higher installed
- `uv` package manager (`pip install uv` if not installed)
- OpenAI API key (for GPT-4/GPT-3.5 access)
- Basic familiarity with FastAPI and SQLAlchemy

## Setup (5 minutes)

### 1. Environment Setup

```bash
# Clone repository and navigate to project
cd /mnt/d/dev/misconcept_platform

# Create virtual environment with uv
uv venv

# Activate virtual environment
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
uv pip install fastapi uvicorn sqlalchemy jinja2 pydantic \
  python-multipart openai httpx pytest pytest-asyncio
```

### 2. Configuration

Create `.env` file in project root:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-your-api-key-here
CHAT_MODEL=gpt-4-turbo
ANALYSIS_MODEL=gpt-3.5-turbo

# Session Security
SESSION_SECRET=change-this-to-random-64-char-string

# Database
DATABASE_URL=sqlite:///./dialogue_sim.db

# Server
HOST=0.0.0.0
PORT=8000
```

### 3. Database Initialization

```bash
# Create database and seed initial data
python -m src.db.seed

# Verify tables created
sqlite3 dialogue_sim.db ".tables"
# Expected output: user, scenario, session, message, etc.
```

## Project Structure

```text
src/
├── models/         # SQLAlchemy ORM models
├── services/       # Business logic (LLM bots, analyzers)
├── api/            # FastAPI routes
├── templates/      # Jinja2 HTML templates
├── db/             # Database utilities
└── prompts/        # LLM prompt templates

tests/
├── contract/       # API endpoint contract tests
├── integration/    # End-to-end flow tests
└── unit/           # Service and model unit tests
```

## Development Workflow (TDD)

### Step 1: Write Failing Contract Test

```python
# tests/contract/test_auth_endpoints.py
def test_login_post_creates_session(client):
    """Test POST /login creates session cookie"""
    response = client.post("/login", data={
        "student_uid": "test_001",
        "nickname": "Test Teacher"
    })

    assert response.status_code == 303  # Redirect
    assert "session_id" in response.cookies
    assert response.headers["Location"] == "/scenarios"
```

Run test (expect FAIL):
```bash
pytest tests/contract/test_auth_endpoints.py::test_login_post_creates_session
```

### Step 2: Write Failing Unit Test

```python
# tests/unit/test_models.py
def test_user_unique_constraint(db_session):
    """Test (student_uid, nickname) uniqueness"""
    user1 = User(student_uid="test", nickname="Teacher")
    db_session.add(user1)
    db_session.commit()

    user2 = User(student_uid="test", nickname="Teacher")
    db_session.add(user2)

    with pytest.raises(IntegrityError):
        db_session.commit()
```

Run test (expect FAIL):
```bash
pytest tests/unit/test_models.py::test_user_unique_constraint
```

### Step 3: Implement Minimum Code

```python
# src/models/user.py
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import UniqueConstraint

class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_uid: Mapped[str] = mapped_column()
    nickname: Mapped[str] = mapped_column()
    role: Mapped[str] = mapped_column(default="teacher")

    __table_args__ = (
        UniqueConstraint("student_uid", "nickname"),
    )
```

```python
# src/api/routes/auth.py
from fastapi import APIRouter, Form, Response
from starlette.responses import RedirectResponse

router = APIRouter()

@router.post("/login")
async def login(
    student_uid: str = Form(),
    nickname: str = Form(),
    response: Response
):
    # Create or get user
    user = get_or_create_user(student_uid, nickname)

    # Set session cookie
    response.set_cookie("session_id", generate_session_id(user.id))

    return RedirectResponse("/scenarios", status_code=303)
```

### Step 4: Run Tests (expect PASS)

```bash
pytest tests/contract/test_auth_endpoints.py::test_login_post_creates_session
pytest tests/unit/test_models.py::test_user_unique_constraint
```

### Step 5: Refactor with Confidence

```python
# Extract validation logic
def validate_student_uid(uid: str) -> str:
    if not 3 <= len(uid) <= 50:
        raise ValueError("student_uid must be 3-50 characters")
    if not uid.replace("_", "").isalnum():
        raise ValueError("student_uid must be alphanumeric + underscore")
    return uid
```

## Running the Application

### Development Server

```bash
# Start with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Visit: http://localhost:8000

### Running Tests

```bash
# All tests
pytest

# Specific test type
pytest tests/contract/
pytest tests/unit/
pytest tests/integration/

# With coverage
pytest --cov=src --cov-report=html
```

## Common Development Tasks

### Adding a New API Endpoint

1. Write contract test in `tests/contract/test_*_endpoints.py`
2. Run test, expect FAIL
3. Add route in `src/api/routes/*.py`
4. Add Pydantic schemas in `src/api/schemas.py`
5. Run test, expect PASS
6. Add OpenAPI documentation in `contracts/*.yaml`

### Adding a New Model

1. Write unit test in `tests/unit/test_models.py`
2. Create model file `src/models/<entity>.py`
3. Add validation rules
4. Create migration (if using Alembic)
5. Update `data-model.md` documentation

### Integrating New LLM Feature

1. Write integration test with mocked LLM response
2. Create service module in `src/services/<feature>.py`
3. Add prompt template in `src/prompts/<feature>.txt`
4. Implement LLM call with error handling
5. Update `research.md` with prompt engineering notes

## Debugging Tips

### Database Inspection

```bash
# View all sessions
sqlite3 dialogue_sim.db "SELECT * FROM session ORDER BY started_at DESC
  LIMIT 10;"

# View messages for session
sqlite3 dialogue_sim.db "SELECT role, content FROM message WHERE
  session_id = 1 ORDER BY created_at;"
```

### LLM Call Logging

```python
# Add to src/services/student_bot.py
import logging
logger = logging.getLogger(__name__)

# Log every LLM call
logger.info(f"LLM Request: {prompt[:100]}...")
logger.info(f"LLM Response: {response[:100]}...")
```

### HTMX Debugging

```html
<!-- Add to templates/layout.html for HTMX debug logging -->
<script>
  htmx.logger = function(elt, event, data) {
    if(console) console.log(event, elt, data);
  }
</script>
```

## Next Steps

1. **Implement User Story 1** (Teacher Conducts Dialogue):
   - Auth endpoints → Scenario list → Chat interface
   - Follow TDD workflow for each component

2. **Integrate LLM Services**:
   - Student bot with scenario-based prompts
   - Tutor bot with intervention rules
   - Analysis bot with framework classification

3. **Add Frontend Interactivity**:
   - HTMX partial updates for messages
   - Analysis badge display
   - Frequency chart visualization

4. **Deploy to Production**:
   - Configure `uvicorn --workers 4`
   - Set production environment variables
   - Enable HTTPS (use reverse proxy like nginx)

## Troubleshooting

**Issue**: `ModuleNotFoundError: No module named 'src'`
**Solution**: Ensure virtual environment is activated and dependencies
installed via `uv pip install -r requirements.txt`

**Issue**: OpenAI API rate limit errors
**Solution**: Implement exponential backoff in LLM service, use caching
for repeated prompts

**Issue**: SQLite locked database error
**Solution**: Enable WAL mode: `sqlite3 dialogue_sim.db "PRAGMA
journal_mode=WAL;"`

**Issue**: Session cookie not persisting
**Solution**: Verify `SESSION_SECRET` is set, check `same_site` and
`secure` cookie attributes match environment

## Resources

- FastAPI documentation: https://fastapi.tiangolo.com/
- SQLAlchemy 2.x: https://docs.sqlalchemy.org/en/20/
- HTMX examples: https://htmx.org/examples/
- OpenAI API: https://platform.openai.com/docs/
- Project spec: [spec.md](./spec.md)
- Data model: [data-model.md](./data-model.md)
- API contracts: [contracts/](./contracts/)
