"""Pytest configuration and shared fixtures."""

import os
from datetime import datetime, timedelta
from typing import AsyncGenerator

import pytest

# Set testing mode BEFORE any imports
os.environ["TESTING"] = "true"


def _has_real_openai_key() -> bool:
    """Return True when a usable OpenAI key is present in the shell env.

    TESTING mode disables .env loading (src/config.py), so tests that
    exercise real LLM calls only work when OPENAI_API_KEY is exported
    in the shell. In pre-commit runs that is typically not the case.
    """
    key = os.environ.get("OPENAI_API_KEY", "")
    return key.startswith("sk-") and "test" not in key.lower() and len(key) > 20


requires_openai_api_key = pytest.mark.skipif(
    not _has_real_openai_key(),
    reason="Requires a real OPENAI_API_KEY exported in the shell",
)


# Import and configure BEFORE importing main
from src.config import config

config.TESTING = True

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db_session
from src.db.connection import Base
from src.main import app
from src.models.analysis_framework import AnalysisFramework
from src.models.message import Message
from src.models.question_analysis import QuestionAnalysis
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.session_summary import SessionSummary
from src.models.user import User

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _set_test_sqlite_pragma(dbapi_conn, connection_record):
    """Apply same SQLite pragmas as production for test fidelity."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with schema."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine.sync_engine, "connect", _set_test_sqlite_pragma)
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create async test database session (alias for db_session)."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine.sync_engine, "connect", _set_test_sqlite_pragma)
    async_session_maker = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def async_client(
    async_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""

    async def override_get_db():
        try:
            yield async_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=True,  # Handle 303 redirects from login
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_client(db_session: AsyncSession) -> TestClient:
    """Create FastAPI test client with test database."""

    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_db_session(
    async_session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """Alias for async_session fixture."""
    yield async_session


@pytest.fixture(scope="function")
async def test_framework(
    async_db_session: AsyncSession,
) -> AnalysisFramework:
    """Create test analysis framework."""
    framework = AnalysisFramework(
        name="Test Framework",
        description="Framework for testing",
        labels_json='["Pressing","Linking","Directing","Recall"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()
    return framework


@pytest.fixture(scope="function")
async def test_student_template(async_db_session: AsyncSession):
    """Create test student bot template."""
    from src.models.prompt_template import PromptTemplate

    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text="You are a test student bot.",
    )
    async_db_session.add(template)
    await async_db_session.flush()
    return template


@pytest.fixture(scope="function")
async def test_tutor_template(async_db_session: AsyncSession):
    """Create test tutor bot template."""
    from src.models.prompt_template import PromptTemplate

    template = PromptTemplate(
        bot_type="tutor",
        template_name="Test Tutor Template",
        version=1,
        template_text="You are a test tutor bot.",
    )
    async_db_session.add(template)
    await async_db_session.flush()
    return template


@pytest.fixture(scope="function")
async def test_teacher(async_db_session: AsyncSession) -> User:
    """Create test teacher user."""
    user = User(
        username="teacher_001",
        nickname="테스트교사",
        role="teacher",
    )
    user.set_password("test1234")
    async_db_session.add(user)
    await async_db_session.flush()
    return user


@pytest.fixture(scope="function")
async def test_scenario(
    async_db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template,
) -> Scenario:
    """Create test scenario."""
    scenario = Scenario(
        title="Test Scenario",
        prompt="Test prompt for scenario",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    async_db_session.add(scenario)
    await async_db_session.flush()
    return scenario


@pytest.fixture(scope="function")
async def sample_session_with_messages(
    async_db_session: AsyncSession,
    test_scenario: Scenario,
    test_teacher: User,
) -> Session:
    """Create session with messages for testing."""
    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=test_teacher.id,
        started_at=datetime.utcnow() - timedelta(hours=1),
        ended_at=datetime.utcnow(),
    )
    async_db_session.add(session)
    await async_db_session.flush()

    messages = [
        Message(
            session_id=session.id,
            role="teacher",
            content="What is photosynthesis?",
        ),
        Message(
            session_id=session.id,
            role="student",
            content="Plants make food from sunlight.",
        ),
    ]
    async_db_session.add_all(messages)
    await async_db_session.commit()
    await async_db_session.refresh(session)
    return session


@pytest.fixture(scope="function")
async def sample_session_with_analysis(
    async_db_session: AsyncSession,
    sample_session_with_messages: Session,
) -> Session:
    """Create session with QuestionAnalysis for testing."""
    from sqlalchemy import select

    result = await async_db_session.execute(
        select(Message).where(
            Message.session_id == sample_session_with_messages.id,
            Message.role == "teacher",
        )
    )
    teacher_msg = result.scalar_one()
    analysis = QuestionAnalysis(
        message_id=teacher_msg.id,
        label="Pressing",
        confidence=0.85,
        meta_json='{"summary":"Test reasoning"}',
    )
    async_db_session.add(analysis)
    await async_db_session.commit()
    return sample_session_with_messages


@pytest.fixture(scope="function")
async def sample_session_with_summary(
    async_db_session: AsyncSession,
    sample_session_with_messages: Session,
) -> Session:
    """Create session with SessionSummary for testing."""
    summary = SessionSummary(
        session_id=sample_session_with_messages.id,
        distribution_json='{"Pressing":1,"Linking":0}',
        feedback="Good questioning technique.",
    )
    async_db_session.add(summary)
    await async_db_session.commit()
    return sample_session_with_messages


@pytest.fixture(scope="function")
async def multiple_sessions(
    async_db_session: AsyncSession,
    test_scenario: Scenario,
    test_teacher: User,
) -> list[Session]:
    """Create multiple sessions for bulk export testing."""
    sessions = []
    for i in range(3):
        s = Session(
            scenario_id=test_scenario.id,
            teacher_id=test_teacher.id,
            started_at=datetime.utcnow() - timedelta(days=i + 1),
            ended_at=datetime.utcnow() - timedelta(days=i),
        )
        async_db_session.add(s)
        await async_db_session.flush()
        msg = Message(session_id=s.id, role="teacher", content=f"Q{i}")
        async_db_session.add(msg)
        sessions.append(s)
    await async_db_session.commit()
    return sessions


# ── Issue #28 — LLM mock fixtures (Stage D) ──────────────────────


@pytest.fixture(scope="function")
def classify_mock(monkeypatch):
    """Stub Analyzer.classify_question to return a fixed result."""
    from unittest.mock import AsyncMock

    mock = AsyncMock(
        return_value={
            "label": "Pressing",
            "confidence": 0.9,
            "reasoning": {"summary": "Test reasoning"},
        }
    )
    monkeypatch.setattr(
        "src.services.analyzer.Analyzer.classify_question", mock
    )
    return mock


@pytest.fixture(scope="function")
def greeting_mock(monkeypatch):
    """Stub Analyzer.detect_greetings to mark nothing as greeting."""
    from unittest.mock import AsyncMock

    mock = AsyncMock(
        side_effect=lambda contents: [{"is_greeting": False} for _ in contents]
    )
    monkeypatch.setattr("src.services.analyzer.Analyzer.detect_greetings", mock)
    return mock


@pytest.fixture(scope="function")
def synthesis_mock(monkeypatch):
    """Stub SessionSynthesizer.synthesize to return a fixed payload.

    Fixture payload matches a realistic session with brief_feedback,
    strengths, improvements, and dialogue_coaching entries.
    """
    from unittest.mock import AsyncMock

    fixed_payload = {
        "version": 1,
        "brief_feedback": [
            "학생 풀이 과정을 물어본 것은 좋은 출발이었어요!",
            "핵심 단서를 더 깊이 탐색했다면 오개념에 빨리 다가갔을 거예요.",
            "다음에는 '왜 그렇게 생각했어?'로 되묻는 연습을 해보세요.",
        ],
        "strengths": [
            {
                "message_id": 1,
                "quote": "어떻게 답을 구했어?",
                "reason": "풀이 과정을 탐색하는 좋은 첫 질문이에요.",
            },
        ],
        "improvements": [
            {
                "student_message_id": 2,
                "student_quote": "분자끼리 더하고 분모끼리 더했어요",
                "missed_reason": "오개념 핵심 단서가 있었어요.",
                "alternative_question": "왜 분자끼리 더해도 된다고 생각했어?",
                "alternative_reason": (
                    "학생의 답변 속 핵심 단어를 잡아서 "
                    "되물으면 논리를 점검해요."
                ),
            },
        ],
        "dialogue_coaching": [
            {
                "message_id": 1,
                "role": "teacher",
                "marker": "good_moment",
                "note": "첫 탐색 질문",
            },
            {
                "message_id": 2,
                "role": "student",
                "marker": "key_clue",
                "note": "오개념 핵심 단서",
            },
        ],
    }
    mock = AsyncMock(return_value=(fixed_payload, "ok"))
    monkeypatch.setattr(
        "src.services.session_synthesizer.SessionSynthesizer.synthesize",
        mock,
    )
    return mock


@pytest.fixture(scope="function")
def synthesis_mock_degraded(monkeypatch):
    """Synthesis mock returning degraded status (partial payload)."""
    from unittest.mock import AsyncMock

    payload = {
        "version": 1,
        "brief_feedback": ["좋은 출발이었어요!"],
        "strengths": [],
        "improvements": [],
        "dialogue_coaching": [],
    }
    mock = AsyncMock(return_value=(payload, "degraded"))
    monkeypatch.setattr(
        "src.services.session_synthesizer.SessionSynthesizer.synthesize",
        mock,
    )
    return mock


@pytest.fixture(scope="function")
def synthesis_mock_failed(monkeypatch):
    """Synthesis mock returning failed status."""
    from unittest.mock import AsyncMock

    payload = {
        "version": 1,
        "brief_feedback": [
            (
                "분석에 실패했습니다. "
                "잠시 후 다시 시도하거나 관리자에게 문의하세요."
            )
        ],
        "strengths": [],
        "improvements": [],
        "dialogue_coaching": [],
    }
    mock = AsyncMock(return_value=(payload, "failed"))
    monkeypatch.setattr(
        "src.services.session_synthesizer.SessionSynthesizer.synthesize",
        mock,
    )
    return mock


@pytest.fixture(scope="function")
def synthesis_mock_raises(monkeypatch):
    """Synthesis mock that raises an exception (simulates LLM failure)."""
    from unittest.mock import AsyncMock

    mock = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    monkeypatch.setattr(
        "src.services.session_synthesizer.SessionSynthesizer.synthesize",
        mock,
    )
    return mock


# ── Authenticated client fixtures ─────────────────────────────────────


@pytest.fixture(scope="function")
async def test_admin(async_db_session: AsyncSession) -> User:
    """Create test admin user."""
    user = User(
        username="admin_001",
        nickname="테스트관리자",
        role="admin",
    )
    user.set_password("test1234")
    async_db_session.add(user)
    await async_db_session.flush()
    return user


@pytest.fixture(scope="function")
async def authenticated_async_client(
    async_client: AsyncClient,
    test_teacher: User,
) -> AsyncClient:
    """Async client pre-authenticated as test_teacher."""
    await async_client.post(
        "/login",
        data={
            "username": test_teacher.username,
            "password": "test1234",
        },
    )
    return async_client


@pytest.fixture(scope="function")
async def admin_async_client(
    async_client: AsyncClient,
    test_admin: User,
) -> AsyncClient:
    """Async client pre-authenticated as test_admin."""
    await async_client.post(
        "/login",
        data={
            "username": test_admin.username,
            "password": "test1234",
        },
    )
    return async_client
