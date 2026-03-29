"""Contract tests for session status filter functionality."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.user import User


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(
        username="admin_filter_001",
        nickname="Admin Filter",
        role="admin",
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def teacher_user(db_session: AsyncSession) -> User:
    """Create a teacher user for testing."""
    user = User(
        username="teacher_filter_001",
        nickname="Teacher Filter",
        role="teacher",
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
    """Create test analysis framework."""
    framework = AnalysisFramework(
        name="Filter Test Framework",
        description="Framework for filter tests",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(framework)
    await db_session.flush()
    return framework


@pytest.fixture
async def test_student_template(
    db_session: AsyncSession,
) -> PromptTemplate:
    """Create test student template."""
    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text="You are a test student bot.",
    )
    db_session.add(template)
    await db_session.flush()
    return template


@pytest.fixture
async def test_scenario(
    db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template: PromptTemplate,
) -> Scenario:
    """Create a test scenario."""
    scenario = Scenario(
        title="Filter Test Scenario",
        prompt="Test prompt",
        student_profile="Test profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


@pytest.fixture
async def mixed_sessions(
    db_session: AsyncSession,
    test_scenario: Scenario,
    teacher_user: User,
) -> list[Session]:
    """Create a mix of active and completed sessions."""
    sessions = []
    now = datetime.utcnow()

    # Create 3 completed sessions
    for i in range(3):
        session = Session(
            scenario_id=test_scenario.id,
            teacher_id=teacher_user.id,
            started_at=now - timedelta(hours=i + 2),
            ended_at=now - timedelta(hours=i + 1),
        )
        db_session.add(session)
        sessions.append(session)

    # Create 2 active sessions
    for i in range(2):
        session = Session(
            scenario_id=test_scenario.id,
            teacher_id=teacher_user.id,
            started_at=now - timedelta(minutes=30 + i * 10),
            ended_at=None,
        )
        db_session.add(session)
        sessions.append(session)

    await db_session.commit()
    for s in sessions:
        await db_session.refresh(s)
    return sessions


class TestSessionStatusFilter:
    """Test session listing page."""

    def test_sessions_page_default_shows_all(
        self,
        test_client: TestClient,
        admin_user: User,
        mixed_sessions: list[Session],
    ):
        """Test that default (no filter) shows all sessions."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        response = test_client.get("/admin/sessions-page")

        assert response.status_code == 200
        html = response.text

        # Should show both completed and active sessions
        assert "완료" in html
        assert "진행중" in html
        # Total: 3 completed + 2 active = 5 sessions
        assert html.count('badge-success">완료</span>') == 3
        assert html.count('badge-warning">진행중</span>') == 2

    def test_download_button_visible_for_completed_sessions(
        self,
        test_client: TestClient,
        admin_user: User,
        mixed_sessions: list[Session],
    ):
        """Test that CSV download button appears for completed sessions."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        response = test_client.get("/admin/sessions-page")

        assert response.status_code == 200
        html = response.text

        # Download button should be visible for completed sessions
        assert "CSV" in html
        assert "btn-success" in html
