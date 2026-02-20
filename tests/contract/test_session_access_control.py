"""Contract tests for session access control (API Security Review).

Tests validate_scenario_access enforcement on session creation,
/metrics admin-only access, and group-based scenario access.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    PromptTemplate,
    Scenario,
    ScenarioGroup,
    User,
    UserGroup,
)


@pytest.fixture(autouse=True)
async def seed_access_control_data(db_session: AsyncSession):
    """Seed additional users for access control tests.

    The contract conftest already creates:
    - test_group (group_id=1)
    - student_001, user1, user2 (teachers in test_group)
    - scenario (id=1, active, linked to test_group)

    This fixture adds:
    - admin_user (admin, in test_group)
    - other_group + other_teacher (teacher in different group)
    - no_group_teacher (teacher with no group)
    - inactive_scenario (is_active=0)
    - deleted_scenario (deleted_at set)
    """
    from datetime import datetime, timezone

    # Admin user
    admin = User(
        username="admin_user",
        nickname="관리자",
        role="admin",
        group_id=1,
    )
    admin.set_password("test1234")
    db_session.add(admin)

    # Another group
    other_group = UserGroup(
        name="Other Group",
        description="A different group",
    )
    db_session.add(other_group)
    await db_session.flush()

    # Teacher in different group
    other_teacher = User(
        username="other_teacher",
        nickname="다른그룹교사",
        role="teacher",
        group_id=other_group.id,
    )
    other_teacher.set_password("test1234")
    db_session.add(other_teacher)

    # Teacher with no group
    no_group_teacher = User(
        username="no_group_teacher",
        nickname="무소속교사",
        role="teacher",
        group_id=None,
    )
    no_group_teacher.set_password("test1234")
    db_session.add(no_group_teacher)

    # Need framework + template for extra scenarios
    from src.models import AnalysisFramework

    fw = AnalysisFramework(
        name="Extra Framework",
        description="For access control tests",
        labels_json='["A","B"]',
    )
    db_session.add(fw)
    await db_session.flush()

    tmpl = PromptTemplate(
        bot_type="student",
        template_name="Extra Template",
        version=1,
        template_text="Extra template.",
    )
    db_session.add(tmpl)
    await db_session.flush()

    # Inactive scenario (linked to test_group)
    inactive = Scenario(
        title="Inactive Scenario",
        prompt="Inactive prompt",
        student_profile="Inactive profile",
        framework_id=fw.id,
        student_template_id=tmpl.id,
        is_active=0,
    )
    db_session.add(inactive)
    await db_session.flush()

    sg_inactive = ScenarioGroup(
        scenario_id=inactive.id,
        group_id=1,
    )
    db_session.add(sg_inactive)

    # Deleted scenario
    deleted = Scenario(
        title="Deleted Scenario",
        prompt="Deleted prompt",
        student_profile="Deleted profile",
        framework_id=fw.id,
        student_template_id=tmpl.id,
        is_active=1,
        deleted_at=datetime.now(timezone.utc),
    )
    db_session.add(deleted)
    await db_session.flush()

    sg_deleted = ScenarioGroup(
        scenario_id=deleted.id,
        group_id=1,
    )
    db_session.add(sg_deleted)

    await db_session.commit()


def _login(client: TestClient, username: str) -> dict:
    """Login helper, returns cookies."""
    resp = client.post(
        "/login",
        data={
            "username": username,
            "password": "test1234",
        },
    )
    return resp.cookies


class TestSessionCreationAccessControl:
    """POST /sessions access control tests."""

    def test_same_group_teacher_can_create_session(
        self, test_client: TestClient
    ):
        """Teacher in scenario's group -> 201."""
        cookies = _login(test_client, "student_001")
        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        assert resp.status_code == 201

    def test_different_group_teacher_gets_403(self, test_client: TestClient):
        """Teacher in different group -> 403."""
        cookies = _login(test_client, "other_teacher")
        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        assert resp.status_code == 403

    def test_deleted_scenario_returns_404(self, test_client: TestClient):
        """Deleted scenario -> 404."""
        cookies = _login(test_client, "student_001")
        # Deleted scenario has deleted_at set
        # Find its ID (it's the last scenario seeded)

        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 9999},
            cookies=cookies,
        )
        assert resp.status_code == 404

    def test_inactive_scenario_returns_404_for_teacher(
        self, test_client: TestClient
    ):
        """Inactive scenario -> 404 for non-admin."""
        cookies = _login(test_client, "student_001")
        # Inactive scenario is id=2 (seeded after default)
        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 2},
            cookies=cookies,
        )
        assert resp.status_code == 404

    def test_nonexistent_scenario_returns_404(self, test_client: TestClient):
        """Non-existent scenario_id -> 404."""
        cookies = _login(test_client, "student_001")
        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 99999},
            cookies=cookies,
        )
        assert resp.status_code == 404

    def test_admin_can_access_other_group_scenario(
        self, test_client: TestClient
    ):
        """Admin bypasses group check -> 201."""
        cookies = _login(test_client, "admin_user")
        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        assert resp.status_code == 201

    def test_admin_can_access_inactive_scenario(self, test_client: TestClient):
        """Admin can create session for inactive scenario -> 201."""
        cookies = _login(test_client, "admin_user")
        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 2},
            cookies=cookies,
        )
        assert resp.status_code == 201

    def test_no_group_teacher_gets_403(self, test_client: TestClient):
        """Teacher with group_id=None -> 403."""
        cookies = _login(test_client, "no_group_teacher")
        resp = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        assert resp.status_code == 403


class TestMetricsAccessControl:
    """GET /metrics access control tests."""

    def test_unauthenticated_metrics_redirects(self, test_client: TestClient):
        """Unauthenticated -> redirect to login (303)."""
        resp = test_client.get("/metrics", follow_redirects=False)
        assert resp.status_code == 303
        assert "/login" in resp.headers["location"]

    def test_teacher_metrics_returns_403(self, test_client: TestClient):
        """Non-admin teacher -> 403."""
        cookies = _login(test_client, "student_001")
        resp = test_client.get("/metrics", cookies=cookies)
        assert resp.status_code == 403

    def test_admin_metrics_returns_200(self, test_client: TestClient):
        """Admin -> 200 with metrics data."""
        cookies = _login(test_client, "admin_user")
        resp = test_client.get("/metrics", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "database" in data
