"""Pytest configuration and shared fixtures."""

import asyncio
import os
import pytest
from datetime import datetime, timedelta
from typing import AsyncGenerator

# Set testing mode BEFORE any imports
os.environ["TESTING"] = "true"

# Import and configure BEFORE importing main
from src.config import config

config.TESTING = True

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.db.connection import Base
from src.main import app
from src.api.dependencies import get_db_session
from src.models.user import User
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.message import Message
from src.models.analysis_framework import AnalysisFramework
from src.models.question_analysis import QuestionAnalysis
from src.models.session_summary import SessionSummary


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with schema."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=None,  # Disable connection pooling for tests
    )
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
        poolclass=None,
    )
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
async def test_teacher(async_db_session: AsyncSession) -> User:
    """Create test teacher user."""
    user = User(
        student_uid="teacher_001",
        nickname="테스트교사",
        role="teacher",
    )
    async_db_session.add(user)
    await async_db_session.flush()
    return user


@pytest.fixture(scope="function")
async def test_scenario(
    async_db_session: AsyncSession,
    test_framework: AnalysisFramework,
) -> Scenario:
    """Create test scenario."""
    scenario = Scenario(
        title="Test Scenario",
        prompt="Test prompt for scenario",
        student_profile="Test student profile",
        framework_id=test_framework.id,
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
