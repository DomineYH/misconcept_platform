"""Contract tests for admin endpoints (T072-T074, T084-T085, T092-T093)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.scenario import Scenario
from src.models.analysis_framework import AnalysisFramework


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(student_uid="admin_001", nickname="관리자", role="admin")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def teacher_user(db_session: AsyncSession) -> User:
    """Create a teacher user for testing."""
    user = User(
        student_uid="teacher_001", nickname="김교사", role="teacher"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
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
async def test_scenario(
    db_session: AsyncSession, test_framework: AnalysisFramework
) -> Scenario:
    """Create a test scenario."""
    scenario = Scenario(
        title="Test Scenario",
        prompt="Test prompt content",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


class TestAdminDashboard:
    """Test GET /admin endpoint contract compliance (T072)."""

    def test_admin_dashboard_requires_admin_role(
        self, test_client: TestClient, teacher_user: User
    ):
        """Verify non-admin users cannot access admin dashboard."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "student_uid": teacher_user.student_uid,
                "nickname": teacher_user.nickname,
            },
        )

        # Try to access admin dashboard
        response = test_client.get("/admin")

        # Contract: 403 Forbidden for non-admin users
        assert response.status_code == 403
        assert "detail" in response.json()

    def test_admin_dashboard_success_for_admin(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify admin users can access admin dashboard."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Access admin dashboard
        response = test_client.get("/admin")

        # Contract: 200 OK with HTML response
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_dashboard_redirects_when_not_logged_in(
        self, test_client: TestClient
    ):
        """Verify unauthenticated users are redirected."""
        response = test_client.get("/admin", follow_redirects=False)

        # Contract: 303 redirect to /login
        assert response.status_code == 303
        assert "/login" in response.headers["location"]


class TestScenarioCreation:
    """Test POST /admin/scenarios endpoint contract compliance (T073)."""

    def test_create_scenario_success(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
    ):
        """Verify successful scenario creation."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Create scenario
        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "New Scenario",
                "prompt": "This is a test prompt for the new scenario.",
                "student_profile": "Test student profile description",
                "framework_id": test_framework.id,
            },
        )

        # Contract: 201 Created with scenario data
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Scenario"
        assert data["is_active"] == 1  # Default active
        assert "id" in data

    def test_create_scenario_title_too_short(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
    ):
        """Verify title length validation (min 3 chars)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Create scenario with short title
        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "AB",  # Too short
                "prompt": "Valid prompt content here.",
                "student_profile": "Valid profile",
                "framework_id": test_framework.id,
            },
        )

        # Contract: 422 Unprocessable Entity (Pydantic validation)
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_scenario_prompt_too_short(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
    ):
        """Verify prompt length validation (min 10 chars)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Create scenario with short prompt
        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Valid Title",
                "prompt": "Short",  # Too short (< 10 chars)
                "student_profile": "Valid profile",
                "framework_id": test_framework.id,
            },
        )

        # Contract: 422 Unprocessable Entity (Pydantic validation)
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_scenario_requires_admin_role(
        self,
        test_client: TestClient,
        teacher_user: User,
        test_framework: AnalysisFramework,
    ):
        """Verify non-admin users cannot create scenarios."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "student_uid": teacher_user.student_uid,
                "nickname": teacher_user.nickname,
            },
        )

        # Try to create scenario
        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "New Scenario",
                "prompt": "Test prompt content",
                "student_profile": "Test profile",
                "framework_id": test_framework.id,
            },
        )

        # Contract: 403 Forbidden
        assert response.status_code == 403


class TestScenarioUpdate:
    """Test PUT /admin/scenarios/{id} endpoint contract compliance (T074)."""

    def test_update_scenario_success(
        self,
        test_client: TestClient,
        admin_user: User,
        test_scenario: Scenario,
    ):
        """Verify successful scenario update."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Update scenario
        response = test_client.put(
            f"/admin/scenarios/{test_scenario.id}",
            json={
                "title": "Updated Title",
                "prompt": "Updated prompt content here.",
            },
        )

        # Contract: 200 OK with updated data
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["prompt"] == "Updated prompt content here."

    def test_toggle_scenario_active_status(
        self,
        test_client: TestClient,
        admin_user: User,
        test_scenario: Scenario,
    ):
        """Verify active status toggle."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Toggle to inactive
        response = test_client.put(
            f"/admin/scenarios/{test_scenario.id}", json={"is_active": 0}
        )

        # Contract: 200 OK with updated status
        assert response.status_code == 200
        assert response.json()["is_active"] == 0

        # Toggle back to active
        response = test_client.put(
            f"/admin/scenarios/{test_scenario.id}", json={"is_active": 1}
        )

        assert response.status_code == 200
        assert response.json()["is_active"] == 1

    def test_update_nonexistent_scenario_returns_404(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify 404 for nonexistent scenario."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Try to update nonexistent scenario
        response = test_client.put(
            "/admin/scenarios/99999",
            json={"title": "Updated Title"},
        )

        # Contract: 404 Not Found
        assert response.status_code == 404

    def test_update_scenario_requires_admin_role(
        self,
        test_client: TestClient,
        teacher_user: User,
        test_scenario: Scenario,
    ):
        """Verify non-admin users cannot update scenarios."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "student_uid": teacher_user.student_uid,
                "nickname": teacher_user.nickname,
            },
        )

        # Try to update scenario
        response = test_client.put(
            f"/admin/scenarios/{test_scenario.id}",
            json={"title": "Updated Title"},
        )

        # Contract: 403 Forbidden
        assert response.status_code == 403
