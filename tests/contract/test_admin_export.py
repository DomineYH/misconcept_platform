"""Contract tests for admin CSV export endpoints."""

import csv
import io
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.message import Message
from src.models.analysis_framework import AnalysisFramework
from src.models.question_analysis import QuestionAnalysis
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(student_uid="admin_export_001", nickname="관리자", role="admin")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def teacher_user(db_session: AsyncSession) -> User:
    user = User(
        student_uid="teacher_export_001", nickname="김교사", role="teacher"
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def second_teacher(db_session: AsyncSession) -> User:
    user = User(
        student_uid="teacher_export_002", nickname="박교사", role="teacher"
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
    fw = AnalysisFramework(
        name="Export Test Framework",
        description="For export tests",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(fw)
    await db_session.flush()
    return fw


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
    scenario = Scenario(
        title="Export Test Scenario",
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
    """Ended session that should be included in export."""
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
        content="Ended session question",
    )
    db_session.add(msg)
    await db_session.flush()

    analysis = QuestionAnalysis(
        message_id=msg.id,
        label="Pressing",
        confidence=0.9,
        meta_json='{"summary":"Test meta"}',
    )
    db_session.add(analysis)
    await db_session.commit()
    return session


@pytest.fixture
async def active_session(
    db_session: AsyncSession,
    test_scenario: Scenario,
    teacher_user: User,
) -> Session:
    """Active session (no ended_at) that should be excluded from export."""
    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_user.id,
        started_at=datetime.utcnow() - timedelta(minutes=30),
        ended_at=None,
    )
    db_session.add(session)
    await db_session.flush()

    msg = Message(
        session_id=session.id,
        role="teacher",
        content="Active session question",
    )
    db_session.add(msg)
    await db_session.commit()
    return session


@pytest.fixture
async def second_teacher_session(
    db_session: AsyncSession,
    test_scenario: Scenario,
    second_teacher: User,
) -> Session:
    """Ended session from different teacher for filter testing."""
    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=second_teacher.id,
        started_at=datetime.utcnow() - timedelta(hours=3),
        ended_at=datetime.utcnow() - timedelta(hours=2),
    )
    db_session.add(session)
    await db_session.flush()

    msg = Message(
        session_id=session.id, role="teacher", content="Second teacher Q"
    )
    db_session.add(msg)
    await db_session.commit()
    return session


class TestAdminExportEndedOnly:
    """Verify export only includes ended sessions."""

    def test_export_excludes_active_sessions(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
        active_session: Session,
    ):
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.get("/admin/sessions/export")
        assert response.status_code == 200

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        session_ids = {r["session_id"] for r in rows}

        assert str(ended_session.id) in session_ids
        assert str(active_session.id) not in session_ids


class TestAdminExportTeacherFilter:
    """Verify teacher_id filter works correctly."""

    def test_export_filter_by_teacher(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
        second_teacher_session: Session,
        teacher_user: User,
    ):
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.get(
            f"/admin/sessions/export?teacher_id={teacher_user.id}"
        )
        assert response.status_code == 200

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        for row in rows:
            assert row["teacher_id"] == str(teacher_user.id)


class TestAdminExportTeacherInfo:
    """Verify export includes raw teacher info and meta_json."""

    def test_export_includes_teacher_nickname(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
        teacher_user: User,
    ):
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.get("/admin/sessions/export")
        assert response.status_code == 200

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        assert len(rows) > 0

        row = rows[0]
        assert "teacher_nickname" in reader.fieldnames
        assert "teacher_student_uid" in reader.fieldnames
        assert row["teacher_nickname"] == teacher_user.nickname
        assert row["teacher_student_uid"] == teacher_user.student_uid

    def test_export_includes_meta_json(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
    ):
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.get("/admin/sessions/export")
        assert response.status_code == 200

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        teacher_rows = [r for r in rows if r["role"] == "teacher"]
        assert len(teacher_rows) > 0

        assert "meta_json" in reader.fieldnames
        assert teacher_rows[0]["meta_json"] != ""


class TestAdminExportSelected:
    """Verify POST /admin/sessions/export-selected endpoint."""

    def test_export_selected_sessions(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
        second_teacher_session: Session,
    ):
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.post(
            "/admin/sessions/export-selected",
            data={"session_ids": [ended_session.id]},
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        session_ids = {r["session_id"] for r in rows}

        assert str(ended_session.id) in session_ids
        assert str(second_teacher_session.id) not in session_ids

    def test_export_selected_rejects_active_session(
        self,
        test_client: TestClient,
        admin_user: User,
        active_session: Session,
    ):
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.post(
            "/admin/sessions/export-selected",
            data={"session_ids": [active_session.id]},
        )
        assert response.status_code == 400
