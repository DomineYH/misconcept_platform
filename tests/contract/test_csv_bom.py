"""Contract tests for UTF-8 BOM in CSV exports.

All CSV download endpoints must include UTF-8 BOM (\\xef\\xbb\\xbf)
for Windows Excel compatibility with Korean text.
"""

import csv
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.message import Message
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.scenario_group import ScenarioGroup
from src.models.session import Session
from src.models.user import User
from src.models.user_group import UserGroup


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        username="bom_admin_001",
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
    test_group: UserGroup,
) -> User:
    user = User(
        username="bom_teacher_001",
        nickname="김교사",
        role="teacher",
        group_id=test_group.id,
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(
        name="BOM Test Group",
        description="Group for BOM tests",
    )
    db_session.add(group)
    await db_session.flush()
    return group


@pytest.fixture
async def test_framework(
    db_session: AsyncSession,
) -> AnalysisFramework:
    fw = AnalysisFramework(
        name="BOM Test Framework",
        description="For BOM tests",
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
        template_name="BOM Test Student",
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
        title="BOM Test Scenario",
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
async def scenario_group(
    db_session: AsyncSession,
    test_scenario: Scenario,
    test_group: UserGroup,
) -> ScenarioGroup:
    sg = ScenarioGroup(
        scenario_id=test_scenario.id,
        group_id=test_group.id,
    )
    db_session.add(sg)
    await db_session.flush()
    return sg


@pytest.fixture
async def ended_session(
    db_session: AsyncSession,
    test_scenario: Scenario,
    teacher_user: User,
) -> Session:
    """Ended session with one message."""
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
        content="BOM 테스트 질문",
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


def _assert_bom_and_valid_csv(response):
    """Assert response has UTF-8 BOM and valid CSV content."""
    assert response.content[:3] == b"\xef\xbb\xbf", (
        "CSV should start with UTF-8 BOM " "for Windows Excel compatibility"
    )

    csv_text = response.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) > 0, "CSV should contain data rows"

    first_field = reader.fieldnames[0]
    assert not first_field.startswith("\ufeff"), (
        "First header should not contain BOM character "
        "after utf-8-sig decoding"
    )


class TestCSVBomPresence:
    """Verify all CSV endpoints include UTF-8 BOM."""

    def test_admin_export_has_utf8_bom(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
    ):
        """GET /admin/sessions/export must start with BOM."""
        _login(test_client, admin_user)

        response = test_client.get("/admin/sessions/export")
        assert response.status_code == 200

        _assert_bom_and_valid_csv(response)

    def test_admin_export_selected_has_utf8_bom(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
    ):
        """POST /admin/sessions/export-selected must start
        with BOM."""
        _login(test_client, admin_user)

        response = test_client.post(
            "/admin/sessions/export-selected",
            data={"session_ids": [ended_session.id]},
        )
        assert response.status_code == 200

        _assert_bom_and_valid_csv(response)

    def test_user_conversations_export_has_utf8_bom(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        ended_session: Session,
    ):
        """GET /admin/user-conversations/{id}/export must
        start with BOM."""
        _login(test_client, admin_user)

        response = test_client.get(
            f"/admin/user-conversations/" f"{teacher_user.id}/export"
        )
        assert response.status_code == 200

        _assert_bom_and_valid_csv(response)

    def test_session_download_has_utf8_bom(
        self,
        test_client: TestClient,
        admin_user: User,
        ended_session: Session,
    ):
        """GET /admin/sessions/{id}/download must start
        with BOM."""
        _login(test_client, admin_user)

        response = test_client.get(
            f"/admin/sessions/{ended_session.id}/download"
        )
        assert response.status_code == 200

        _assert_bom_and_valid_csv(response)

    def test_user_session_export_has_utf8_bom(
        self,
        test_client: TestClient,
        teacher_user: User,
        ended_session: Session,
        scenario_group: ScenarioGroup,
    ):
        """GET /sessions/{id}/export.csv must start with BOM.

        Uses teacher login (session owner), not admin.
        """
        _login(test_client, teacher_user)

        response = test_client.get(f"/sessions/{ended_session.id}/export.csv")
        assert response.status_code == 200

        _assert_bom_and_valid_csv(response)
