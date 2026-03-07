"""Contract tests for user conversation download endpoints.

Tests verify:
- Export downloads all completed sessions (no date filter)
- Session list API returns correct data
- Non-admin access is rejected
- Non-existent user returns 404
"""

import csv
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import (
    AnalysisFramework,
)
from src.models.message import Message
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.user import User


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        username="uc_admin_001",
        nickname="관리자",
        role="admin",
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def teacher_user(
    db_session: AsyncSession,
) -> User:
    user = User(
        username="uc_teacher_001",
        nickname="김교사",
        role="teacher",
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_framework(
    db_session: AsyncSession,
) -> AnalysisFramework:
    fw = AnalysisFramework(
        name="UC Test Framework",
        description="For UC tests",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(fw)
    await db_session.flush()
    return fw


@pytest.fixture
async def test_student_template(
    db_session: AsyncSession,
) -> PromptTemplate:
    template = PromptTemplate(
        bot_type="student",
        template_name="UC Test Student",
        version=1,
        template_text="You are a test student.",
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
    scenario = Scenario(
        title="UC Test Scenario",
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
async def ended_session(
    db_session: AsyncSession,
    test_scenario: Scenario,
    teacher_user: User,
) -> Session:
    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_user.id,
        started_at=datetime.utcnow() - timedelta(hours=2),
        ended_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.flush()

    msg = Message(
        session_id=session.id,
        role="teacher",
        content="Test question",
    )
    db_session.add(msg)
    await db_session.commit()
    return session


@pytest.fixture
async def second_ended_session(
    db_session: AsyncSession,
    test_scenario: Scenario,
    teacher_user: User,
) -> Session:
    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_user.id,
        started_at=datetime.utcnow() - timedelta(days=3),
        ended_at=datetime.utcnow() - timedelta(days=3, hours=-1),
    )
    db_session.add(session)
    await db_session.flush()

    msg = Message(
        session_id=session.id,
        role="teacher",
        content="Old question",
    )
    db_session.add(msg)
    await db_session.commit()
    return session


def _login(client: TestClient, user: User):
    client.post(
        "/login",
        data={
            "username": user.username,
            "password": "test1234",
        },
    )


class TestExportUserConversations:
    """GET /admin/user-conversations/{id}/export"""

    def test_exports_all_completed_sessions(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        ended_session: Session,
        second_ended_session: Session,
    ):
        """Export should include ALL completed sessions."""
        _login(test_client, admin_user)

        response = test_client.get(
            f"/admin/user-conversations/" f"{teacher_user.id}/export"
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        session_ids = {r["session_id"] for r in rows}

        assert str(ended_session.id) in session_ids
        assert str(second_ended_session.id) in session_ids

    def test_no_date_param_accepted(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        ended_session: Session,
        second_ended_session: Session,
    ):
        """date param should NOT filter results
        (feature removed)."""
        _login(test_client, admin_user)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        response = test_client.get(
            f"/admin/user-conversations/"
            f"{teacher_user.id}/export?date={today}"
        )
        assert response.status_code == 200

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        session_ids = {r["session_id"] for r in rows}

        # Both sessions should be present regardless
        # of date param (feature removed)
        assert str(ended_session.id) in session_ids
        assert str(second_ended_session.id) in session_ids

    def test_returns_404_for_nonexistent_user(
        self,
        test_client: TestClient,
        admin_user: User,
    ):
        _login(test_client, admin_user)
        response = test_client.get("/admin/user-conversations/99999/export")
        assert response.status_code == 404

    def test_rejects_non_admin(
        self,
        test_client: TestClient,
        teacher_user: User,
    ):
        _login(test_client, teacher_user)
        response = test_client.get(
            f"/admin/user-conversations/" f"{teacher_user.id}/export"
        )
        assert response.status_code == 403


class TestListUserSessions:
    """GET /admin/user-conversations/{id}/sessions"""

    def test_returns_session_list(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        ended_session: Session,
    ):
        _login(test_client, admin_user)

        response = test_client.get(
            f"/admin/user-conversations/" f"{teacher_user.id}/sessions"
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1

        session_data = data[0]
        assert "id" in session_data
        assert "started_at" in session_data
        assert "scenario_title" in session_data
        assert "message_count" in session_data

    def test_returns_correct_message_count(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        ended_session: Session,
    ):
        _login(test_client, admin_user)

        response = test_client.get(
            f"/admin/user-conversations/" f"{teacher_user.id}/sessions"
        )
        data = response.json()

        s = next(x for x in data if x["id"] == ended_session.id)
        assert s["message_count"] == 1
        assert s["scenario_title"] == "UC Test Scenario"

    def test_returns_404_for_nonexistent_user(
        self,
        test_client: TestClient,
        admin_user: User,
    ):
        _login(test_client, admin_user)
        response = test_client.get("/admin/user-conversations/99999/sessions")
        assert response.status_code == 404

    def test_rejects_non_admin(
        self,
        test_client: TestClient,
        teacher_user: User,
    ):
        _login(test_client, teacher_user)
        response = test_client.get(
            f"/admin/user-conversations/" f"{teacher_user.id}/sessions"
        )
        assert response.status_code == 403
