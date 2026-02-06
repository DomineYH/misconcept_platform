"""Integration tests for scenario deletion (soft delete)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user."""
    user = User(
        username="admin_001", nickname="관리자", role="admin"
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def teacher_user(db_session: AsyncSession) -> User:
    """Create a teacher user."""
    user = User(
        username="teacher_001", nickname="김교사", role="teacher"
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_framework(
    db_session: AsyncSession,
) -> AnalysisFramework:
    """Create a test framework."""
    framework = AnalysisFramework(
        name="Test Framework",
        description="For testing",
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


class TestScenarioDelete:
    """Test scenario soft delete functionality."""

    def test_delete_scenario_without_sessions(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
        test_student_template: PromptTemplate,
    ):
        """Admin can delete scenario with no sessions."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create scenario
        create_resp = test_client.post(
            "/admin/scenarios",
            json={
                "title": "To Delete",
                "prompt": "This will be deleted",
                "student_profile": "Test",
                "framework_id": test_framework.id,
                "student_template_id": test_student_template.id,
            },
        )
        assert create_resp.status_code == 201
        scenario_id = create_resp.json()["id"]

        # Delete scenario
        delete_resp = test_client.delete(
            f"/admin/scenarios/{scenario_id}"
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"

        # Verify scenario hidden from admin list
        list_resp = test_client.get("/admin/scenarios")
        assert list_resp.status_code == 200
        assert "To Delete" not in list_resp.text

    async def test_force_delete_scenario_with_active_session(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        test_framework: AnalysisFramework,
        test_student_template: PromptTemplate,
        db_session: AsyncSession,
    ):
        """Admin can force delete scenario with active session (soft delete)."""
        # Create scenario
        scenario = Scenario(
            title="With Active Session",
            prompt="Has active session",
            student_profile="Test",
            framework_id=test_framework.id,
            student_template_id=test_student_template.id,
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        # Create active session
        session = Session(
            scenario_id=scenario.id, teacher_id=teacher_user.id
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Admin logs in and deletes scenario
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        delete_resp = test_client.delete(
            f"/admin/scenarios/{scenario.id}"
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"

        # Verify soft delete
        await db_session.refresh(scenario)
        await db_session.refresh(session)
        assert scenario.deleted_at is not None
        assert session.deleted_at is not None

    async def test_force_delete_scenario_with_ended_session(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        test_framework: AnalysisFramework,
        test_student_template: PromptTemplate,
        db_session: AsyncSession,
    ):
        """Admin can force delete scenario with completed session (soft delete)."""
        # Create scenario
        scenario = Scenario(
            title="With Ended Session",
            prompt="Has ended session",
            student_profile="Test",
            framework_id=test_framework.id,
            student_template_id=test_student_template.id,
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        # Create ended session
        session = Session(
            scenario_id=scenario.id, teacher_id=teacher_user.id
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # End session
        from datetime import datetime

        session.ended_at = datetime.utcnow()
        await db_session.commit()

        # Admin logs in and deletes scenario
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        delete_resp = test_client.delete(
            f"/admin/scenarios/{scenario.id}"
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"

        # Verify soft delete
        await db_session.refresh(scenario)
        await db_session.refresh(session)
        assert scenario.deleted_at is not None
        assert session.deleted_at is not None

    async def test_teacher_cannot_delete_scenario(
        self,
        test_client: TestClient,
        teacher_user: User,
        test_framework: AnalysisFramework,
        test_student_template: PromptTemplate,
        db_session: AsyncSession,
    ):
        """Teacher role cannot delete scenarios."""
        # Create scenario directly
        scenario = Scenario(
            title="Teacher Cannot Delete",
            prompt="Test",
            student_profile="Test",
            framework_id=test_framework.id,
            student_template_id=test_student_template.id,
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        # Teacher tries to delete
        test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
            },
        )

        delete_resp = test_client.delete(
            f"/admin/scenarios/{scenario.id}"
        )
        assert delete_resp.status_code == 403

    async def test_deleted_scenario_hidden_from_lists(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        test_framework: AnalysisFramework,
        test_student_template: PromptTemplate,
        db_session: AsyncSession,
    ):
        """Deleted scenarios are hidden from all lists."""
        # Create and soft-delete scenario
        scenario = Scenario(
            title="Hidden Scenario",
            prompt="Test",
            student_profile="Test",
            framework_id=test_framework.id,
            student_template_id=test_student_template.id,
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        scenario.mark_deleted()
        await db_session.commit()

        # Verify hidden from admin list
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )
        admin_resp = test_client.get("/admin/scenarios")
        assert "Hidden Scenario" not in admin_resp.text

        # Verify hidden from teacher list
        test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
            },
        )
        teacher_resp = test_client.get("/scenarios")
        assert "Hidden Scenario" not in teacher_resp.text

        # Verify detail page returns 404
        detail_resp = test_client.get(f"/scenarios/{scenario.id}")
        assert detail_resp.status_code == 404
