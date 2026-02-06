"""Integration test for session filtering workflow (T094)."""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.message import Message
from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
    """Create a test framework."""
    framework = AnalysisFramework(
        name="Test Framework",
        description="For testing session filtering",
        labels_json='["high", "low"]',
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


@pytest.fixture
async def test_student_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test student template."""
    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text=(
            "You are a test student bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_scenario(
    db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template: PromptTemplate,
) -> Scenario:
    """Create a test scenario."""
    scenario = Scenario(
        title="Test Scenario",
        prompt="Test prompt content",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(username="admin_001", nickname="관리자", role="admin")
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def teacher_users(db_session: AsyncSession) -> list[User]:
    """Create multiple teacher users for testing."""
    teacher1 = User(
        username="teacher_001", nickname="김교사", role="teacher"
    )
    teacher1.set_password("test1234")
    teacher2 = User(
        username="teacher_002", nickname="이교사", role="teacher"
    )
    teacher2.set_password("test1234")
    teacher3 = User(
        username="teacher_003", nickname="박교사", role="teacher"
    )
    teacher3.set_password("test1234")
    db_session.add_all([teacher1, teacher2, teacher3])
    await db_session.commit()
    await db_session.refresh(teacher1)
    await db_session.refresh(teacher2)
    await db_session.refresh(teacher3)
    return [teacher1, teacher2, teacher3]


@pytest.fixture
async def test_sessions_multiple_dates(
    db_session: AsyncSession,
    test_scenario: Scenario,
    teacher_users: list[User],
) -> list[Session]:
    """Create sessions with various dates and teachers."""
    now = datetime.utcnow()
    sessions = []

    # Session 1: teacher1, 10 days ago
    session1 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_users[0].id,
        started_at=now - timedelta(days=10),
        ended_at=now - timedelta(days=10, hours=-2),
    )
    db_session.add(session1)
    await db_session.flush()
    msg1 = Message(
        session_id=session1.id,
        role="teacher",
        content="Old session",
        created_at=now - timedelta(days=10),
    )
    db_session.add(msg1)
    sessions.append(session1)

    # Session 2: teacher1, 5 days ago
    session2 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_users[0].id,
        started_at=now - timedelta(days=5),
        ended_at=now - timedelta(days=5, hours=-1),
    )
    db_session.add(session2)
    await db_session.flush()
    msg2 = Message(
        session_id=session2.id,
        role="teacher",
        content="Mid session teacher1",
        created_at=now - timedelta(days=5),
    )
    db_session.add(msg2)
    sessions.append(session2)

    # Session 3: teacher2, 4 days ago
    session3 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_users[1].id,
        started_at=now - timedelta(days=4),
        ended_at=now - timedelta(days=4, hours=-1),
    )
    db_session.add(session3)
    await db_session.flush()
    msg3 = Message(
        session_id=session3.id,
        role="teacher",
        content="Mid session teacher2",
        created_at=now - timedelta(days=4),
    )
    db_session.add(msg3)
    sessions.append(session3)

    # Session 4: teacher2, 2 days ago
    session4 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_users[1].id,
        started_at=now - timedelta(days=2),
        ended_at=now - timedelta(days=2, hours=-1),
    )
    db_session.add(session4)
    await db_session.flush()
    msg4 = Message(
        session_id=session4.id,
        role="teacher",
        content="Recent session teacher2",
        created_at=now - timedelta(days=2),
    )
    db_session.add(msg4)
    sessions.append(session4)

    # Session 5: teacher3, 1 day ago
    session5 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_users[2].id,
        started_at=now - timedelta(days=1),
        ended_at=now - timedelta(days=1, hours=-1),
    )
    db_session.add(session5)
    await db_session.flush()
    msg5 = Message(
        session_id=session5.id,
        role="teacher",
        content="Recent session teacher3",
        created_at=now - timedelta(days=1),
    )
    db_session.add(msg5)
    sessions.append(session5)

    # Session 6: teacher1, active (no ended_at)
    session6 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_users[0].id,
        started_at=now - timedelta(hours=2),
    )
    db_session.add(session6)
    await db_session.flush()
    msg6 = Message(
        session_id=session6.id,
        role="teacher",
        content="Active session",
        created_at=now - timedelta(hours=2),
    )
    db_session.add(msg6)
    sessions.append(session6)

    await db_session.commit()
    for session in sessions:
        await db_session.refresh(session)

    return sessions


class TestSessionFilteringWorkflow:
    """Integration test for session filtering workflow (T094)."""

    def test_filter_by_date_range(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions_multiple_dates: list[Session],
    ):
        """Test filtering sessions by date range."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Filter sessions from 6 days ago to 3 days ago
        # Should return session2 (5 days ago) and session3 (4 days ago)
        date_from = (datetime.utcnow() - timedelta(days=6)).isoformat()
        date_to = (datetime.utcnow() - timedelta(days=3)).isoformat()

        response = test_client.get(
            f"/admin/sessions?date_from={date_from}&date_to={date_to}"
        )

        # Verify correct subset returned
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data

        # Should have sessions 2 and 3 (both in the 6-3 day range)
        session_ids = [s["id"] for s in data["sessions"]]
        assert (
            test_sessions_multiple_dates[1].id in session_ids
        )  # session2
        assert (
            test_sessions_multiple_dates[2].id in session_ids
        )  # session3

        # Should NOT have session1 (too old) or session4-6 (too recent)
        assert (
            test_sessions_multiple_dates[0].id not in session_ids
        )  # session1
        assert (
            test_sessions_multiple_dates[3].id not in session_ids
        )  # session4

    def test_filter_by_teacher(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_users: list[User],
        test_sessions_multiple_dates: list[Session],
    ):
        """Test filtering sessions by specific teacher."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Filter sessions by teacher2 (should have session3 and session4)
        response = test_client.get(
            f"/admin/sessions?teacher_id={teacher_users[1].id}"
        )

        # Verify only teacher2's sessions returned
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data

        # Should have sessions 3 and 4 (both belong to teacher2)
        session_ids = [s["id"] for s in data["sessions"]]
        assert (
            test_sessions_multiple_dates[2].id in session_ids
        )  # session3
        assert (
            test_sessions_multiple_dates[3].id in session_ids
        )  # session4

        # Should NOT have other teachers' sessions
        for session in data["sessions"]:
            assert session["teacher_id"] == teacher_users[1].id

    def test_filter_by_date_and_teacher(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_users: list[User],
        test_sessions_multiple_dates: list[Session],
    ):
        """Test combined date and teacher filtering."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Filter sessions: teacher1 from 7 days ago to now
        # Should return session2 (5 days ago) and session6 (active)
        date_from = (datetime.utcnow() - timedelta(days=7)).isoformat()

        response = test_client.get(
            f"/admin/sessions?date_from={date_from}&teacher_id={teacher_users[0].id}"
        )

        # Verify correct subset returned
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data

        # Should have session2 and session6 (both teacher1, within range)
        session_ids = [s["id"] for s in data["sessions"]]
        assert (
            test_sessions_multiple_dates[1].id in session_ids
        )  # session2
        assert (
            test_sessions_multiple_dates[5].id in session_ids
        )  # session6

        # Should NOT have session1 (too old) or other teachers' sessions
        assert (
            test_sessions_multiple_dates[0].id not in session_ids
        )  # session1

        # All returned sessions should be teacher1
        for session in data["sessions"]:
            assert session["teacher_id"] == teacher_users[0].id

    def test_no_filters_returns_all_sessions(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions_multiple_dates: list[Session],
    ):
        """Test that no filters returns all sessions."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Get all sessions (no filters)
        response = test_client.get("/admin/sessions")

        # Verify all sessions returned
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 6

        # Verify all session IDs present
        session_ids = [s["id"] for s in data["sessions"]]
        for session in test_sessions_multiple_dates:
            assert session.id in session_ids

    def test_date_from_filter_only(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions_multiple_dates: list[Session],
    ):
        """Test filtering with only date_from parameter."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Filter sessions from 3 days ago to now
        # Should return sessions 4, 5, 6
        date_from = (datetime.utcnow() - timedelta(days=3)).isoformat()

        response = test_client.get(f"/admin/sessions?date_from={date_from}")

        # Verify correct subset returned
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data

        # Should have sessions 4, 5, 6
        session_ids = [s["id"] for s in data["sessions"]]
        assert (
            test_sessions_multiple_dates[3].id in session_ids
        )  # session4
        assert (
            test_sessions_multiple_dates[4].id in session_ids
        )  # session5
        assert (
            test_sessions_multiple_dates[5].id in session_ids
        )  # session6

        # Should NOT have older sessions
        assert (
            test_sessions_multiple_dates[0].id not in session_ids
        )  # session1
        assert (
            test_sessions_multiple_dates[1].id not in session_ids
        )  # session2

    def test_date_to_filter_only(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions_multiple_dates: list[Session],
    ):
        """Test filtering with only date_to parameter."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Filter sessions up to 3 days ago
        # Should return sessions 1, 2, 3 (all before/at 3 days ago)
        # Session 4 (2 days ago) is more recent than 3 days ago, so excluded
        date_to = (datetime.utcnow() - timedelta(days=3)).isoformat()

        response = test_client.get(f"/admin/sessions?date_to={date_to}")

        # Verify correct subset returned
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data

        # Should have sessions 1, 2, 3 (all at or before 3 days ago)
        session_ids = [s["id"] for s in data["sessions"]]
        assert (
            test_sessions_multiple_dates[0].id in session_ids
        )  # session1 (10 days ago)
        assert (
            test_sessions_multiple_dates[1].id in session_ids
        )  # session2 (5 days ago)
        assert (
            test_sessions_multiple_dates[2].id in session_ids
        )  # session3 (4 days ago)

        # Should NOT have recent sessions (after 3 days ago)
        assert (
            test_sessions_multiple_dates[3].id not in session_ids
        )  # session4 (2 days ago)
        assert (
            test_sessions_multiple_dates[4].id not in session_ids
        )  # session5 (1 day ago)
