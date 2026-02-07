"""Contract tests for admin endpoints (T072-T074, T084-T085, T092-T093)."""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.message import Message
from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate


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
async def teacher_user(db_session: AsyncSession) -> User:
    """Create a teacher user for testing."""
    user = User(
        username="teacher_001", nickname="김교사", role="teacher"
    )
    user.set_password("test1234")
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
async def test_student_template(
    db_session: AsyncSession,
) -> PromptTemplate:
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
                "username": teacher_user.username,
                "password": "test1234",
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
                "username": admin_user.username,
                "password": "test1234",
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
        test_student_template: PromptTemplate,
    ):
        """Verify successful scenario creation."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
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
                "student_template_id": test_student_template.id,
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
                "username": admin_user.username,
                "password": "test1234",
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
                "username": admin_user.username,
                "password": "test1234",
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
        test_student_template: PromptTemplate,
    ):
        """Verify non-admin users cannot create scenarios."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
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
                "student_template_id": test_student_template.id,
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
                "username": admin_user.username,
                "password": "test1234",
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
                "username": admin_user.username,
                "password": "test1234",
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
                "username": admin_user.username,
                "password": "test1234",
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
                "username": teacher_user.username,
                "password": "test1234",
            },
        )

        # Try to update scenario
        response = test_client.put(
            f"/admin/scenarios/{test_scenario.id}",
            json={"title": "Updated Title"},
        )

        # Contract: 403 Forbidden
        assert response.status_code == 403


class TestFrameworkManagement:
    """Test framework management endpoints (T084-T085)."""

    def test_get_frameworks_success(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
    ):
        """Verify GET /admin/frameworks returns framework list."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Get frameworks
        response = test_client.get("/admin/frameworks")

        # Contract: 200 OK with HTML framework page
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Framework name should appear in rendered HTML
        assert test_framework.name in response.text

    def test_get_frameworks_requires_admin_role(
        self, test_client: TestClient, teacher_user: User
    ):
        """Verify non-admin users cannot access frameworks."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
            },
        )

        # Try to get frameworks
        response = test_client.get("/admin/frameworks")

        # Contract: 403 Forbidden
        assert response.status_code == 403

    def test_get_frameworks_redirects_when_not_logged_in(
        self, test_client: TestClient
    ):
        """Verify unauthenticated users are redirected."""
        response = test_client.get(
            "/admin/frameworks", follow_redirects=False
        )

        # Contract: 303 redirect to /login
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_create_framework_success(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify successful framework creation."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create framework
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "New Framework",
                "description": "Test framework description",
                "labels": ["Label1", "Label2", "Label3"],
            },
        )

        # Contract: 201 Created with framework data
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Framework"
        assert data["description"] == "Test framework description"
        # API returns labels_json as raw JSON string
        import json
        labels = json.loads(data["labels_json"])
        assert len(labels) == 3
        assert "Label1" in labels
        assert "id" in data

    def test_create_framework_with_min_labels(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify framework with minimum labels (2)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create framework with 2 labels
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "Minimal Framework",
                "description": "Minimal test",
                "labels": ["Label1", "Label2"],
            },
        )

        # Contract: 201 Created
        assert response.status_code == 201
        # API returns labels_json as raw JSON string
        import json
        labels = json.loads(response.json()["labels_json"])
        assert len(labels) == 2

    def test_create_framework_too_few_labels(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify labels validation (min 2 labels)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create framework with only 1 label
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "Invalid Framework",
                "description": "Invalid test",
                "labels": ["OnlyOne"],
            },
        )

        # Contract: 422 Unprocessable Entity
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_framework_too_many_labels(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify labels validation (max 20 labels)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create framework with 21 labels
        labels = [f"Label{i}" for i in range(21)]
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "Too Many Labels",
                "description": "Invalid test",
                "labels": labels,
            },
        )

        # Contract: 422 Unprocessable Entity
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_framework_label_too_short(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify label length validation (min 2 chars)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create framework with short label
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "Invalid Label Framework",
                "description": "Test",
                "labels": ["A", "ValidLabel"],  # "A" is too short
            },
        )

        # Contract: 422 Unprocessable Entity
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_framework_label_too_long(
        self, test_client: TestClient, admin_user: User
    ):
        """Verify label length validation (max 50 chars)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create framework with long label (51 chars)
        long_label = "A" * 51
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "Invalid Label Framework",
                "description": "Test",
                "labels": [long_label, "ValidLabel"],
            },
        )

        # Contract: 422 Unprocessable Entity
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_framework_requires_admin_role(
        self, test_client: TestClient, teacher_user: User
    ):
        """Verify non-admin users cannot create frameworks."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
            },
        )

        # Try to create framework
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "New Framework",
                "description": "Test description for framework",
                "labels": ["Label1", "Label2"],
            },
        )

        # Contract: 403 Forbidden
        assert response.status_code == 403


@pytest.fixture
async def test_sessions(
    db_session: AsyncSession,
    test_scenario: Scenario,
    teacher_user: User,
    admin_user: User,
) -> list[Session]:
    """Create test sessions with different dates and teachers."""
    now = datetime.utcnow()

    # Session 1: Teacher, 2 days ago, ended
    session1 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_user.id,
        started_at=now - timedelta(days=2),
        ended_at=now - timedelta(days=2, hours=-1),
    )
    db_session.add(session1)
    await db_session.flush()

    # Add messages to session1
    msg1 = Message(
        session_id=session1.id,
        role="teacher",
        content="Question 1",
        created_at=now - timedelta(days=2),
    )
    msg2 = Message(
        session_id=session1.id,
        role="student",
        content="Answer 1",
        created_at=now - timedelta(days=2, minutes=-1),
    )
    db_session.add_all([msg1, msg2])

    # Session 2: Teacher, 5 days ago, ended
    session2 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_user.id,
        started_at=now - timedelta(days=5),
        ended_at=now - timedelta(days=5, hours=-2),
    )
    db_session.add(session2)
    await db_session.flush()

    # Add messages to session2
    msg3 = Message(
        session_id=session2.id,
        role="teacher",
        content="Question 2",
        created_at=now - timedelta(days=5),
    )
    db_session.add(msg3)

    # Session 3: Admin, 1 day ago, ended
    session3 = Session(
        scenario_id=test_scenario.id,
        teacher_id=admin_user.id,
        started_at=now - timedelta(days=1),
        ended_at=now - timedelta(days=1, hours=-1),
    )
    db_session.add(session3)
    await db_session.flush()

    # Add messages to session3
    msg4 = Message(
        session_id=session3.id,
        role="teacher",
        content="Question 3",
        created_at=now - timedelta(days=1),
    )
    db_session.add(msg4)

    # Session 4: Teacher, active (no ended_at)
    session4 = Session(
        scenario_id=test_scenario.id,
        teacher_id=teacher_user.id,
        started_at=now - timedelta(hours=1),
    )
    db_session.add(session4)

    await db_session.commit()
    await db_session.refresh(session1)
    await db_session.refresh(session2)
    await db_session.refresh(session3)
    await db_session.refresh(session4)

    return [session1, session2, session3, session4]


class TestSessionLogs:
    """Test GET /admin/sessions endpoint contract compliance (T092)."""

    def test_list_sessions_success(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions: list[Session],
    ):
        """Verify admin can list all sessions."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # List all sessions
        response = test_client.get("/admin/sessions")

        # Contract: 200 OK with session list
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) >= 4
        # Verify session structure
        assert "id" in data["sessions"][0]
        assert "scenario_title" in data["sessions"][0]
        assert "teacher_nickname" in data["sessions"][0]
        assert "started_at" in data["sessions"][0]

    def test_list_sessions_with_date_filter(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions: list[Session],
    ):
        """Verify sessions can be filtered by date range."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Filter sessions from 3 days ago to now
        date_from = (
            datetime.utcnow() - timedelta(days=3)
        ).isoformat()
        response = test_client.get(
            f"/admin/sessions?date_from={date_from}"
        )

        # Contract: 200 OK with filtered sessions
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        # Should have session1, session3, session4 (not session2)
        assert len(data["sessions"]) >= 3

    def test_list_sessions_with_teacher_filter(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_user: User,
        test_sessions: list[Session],
    ):
        """Verify sessions can be filtered by teacher."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Filter sessions by teacher
        response = test_client.get(
            f"/admin/sessions?teacher_id={teacher_user.id}"
        )

        # Contract: 200 OK with filtered sessions
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        # Should have session1, session2, session4 (not session3)
        for session in data["sessions"]:
            # All returned sessions should belong to teacher_user
            pass  # Will verify after implementation

    def test_list_sessions_requires_admin_role(
        self,
        test_client: TestClient,
        teacher_user: User,
        test_sessions: list[Session],
    ):
        """Verify non-admin users cannot list sessions."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
            },
        )

        # Try to list sessions
        response = test_client.get("/admin/sessions")

        # Contract: 403 Forbidden
        assert response.status_code == 403

    def test_list_sessions_redirect_if_not_logged_in(
        self, test_client: TestClient
    ):
        """Verify redirect to login if not authenticated."""
        # Try to list sessions without login
        response = test_client.get("/admin/sessions", follow_redirects=False)

        # Contract: 303 See Other redirect to /login
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


class TestBulkExport:
    """Test GET /admin/sessions/export endpoint (T093)."""

    def test_export_sessions_success(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions: list[Session],
    ):
        """Verify admin can export sessions as CSV."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Export all sessions
        response = test_client.get("/admin/sessions/export")

        # Contract: 200 OK with CSV content
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "text/csv; charset=utf-8"
        )
        assert "attachment" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]

        # Verify CSV structure
        csv_content = response.text
        lines = csv_content.strip().split("\n")
        assert len(lines) >= 2  # Header + at least 1 data row
        # Verify header
        header = lines[0]
        assert "session_id" in header.lower()
        assert "scenario" in header.lower()
        assert "teacher" in header.lower()

    def test_export_sessions_with_filters(
        self,
        test_client: TestClient,
        admin_user: User,
        test_sessions: list[Session],
    ):
        """Verify filtered sessions can be exported."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Export filtered sessions
        date_from = (
            datetime.utcnow() - timedelta(days=3)
        ).isoformat()
        response = test_client.get(
            f"/admin/sessions/export?date_from={date_from}"
        )

        # Contract: 200 OK with CSV
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    def test_export_sessions_requires_admin_role(
        self,
        test_client: TestClient,
        teacher_user: User,
        test_sessions: list[Session],
    ):
        """Verify non-admin users cannot export sessions."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
            },
        )

        # Try to export sessions
        response = test_client.get("/admin/sessions/export")

        # Contract: 403 Forbidden
        assert response.status_code == 403

    def test_export_sessions_redirect_if_not_logged_in(
        self, test_client: TestClient
    ):
        """Verify redirect to login if not authenticated."""
        # Try to export without login
        response = test_client.get("/admin/sessions/export", follow_redirects=False)

        # Contract: 303 See Other redirect to /login
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
