"""Integration tests for scenario lifecycle management (T075)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.prompt_template import PromptTemplate
from src.models.user_group import UserGroup
from src.models.scenario_group import ScenarioGroup


@pytest.fixture
async def test_group(db_session: AsyncSession) -> UserGroup:
    """Create a user group for testing."""
    group = UserGroup(
        name="Test Group",
        description="Group for scenario tests",
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return group


@pytest.fixture
async def teacher_with_group(
    db_session: AsyncSession,
    test_group: UserGroup,
) -> User:
    """Create a teacher user assigned to a group."""
    user = User(
        username="teacher_001",
        nickname="김교사",
        role="teacher",
        group_id=test_group.id,
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestScenarioLifecycle:
    """Test complete scenario lifecycle management."""

    def test_scenario_lifecycle_flow(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_with_group: User,
        test_framework: AnalysisFramework,
        test_student_template: PromptTemplate,
        test_group: UserGroup,
        db_session: AsyncSession,
    ):
        """Test: create -> activate -> visibility -> deactivate -> hidden."""

        # Step 1: Admin creates new scenario with group
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        create_response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Lifecycle Test Scenario",
                "prompt": "This is a test scenario for lifecycle testing.",
                "student_profile": "Test student profile",
                "framework_id": test_framework.id,
                "student_template_id": test_student_template.id,
                "group_ids": [test_group.id],
            },
        )

        assert create_response.status_code == 201
        scenario_id = create_response.json()["id"]
        assert create_response.json()["is_active"] == 1

        # Step 2: Teacher logs in
        test_client.post(
            "/login",
            data={
                "username": teacher_with_group.username,
                "password": "test1234",
            },
        )

        # Step 3: Verify scenario is visible to teachers
        scenarios_response = test_client.get("/scenarios")
        assert scenarios_response.status_code == 200
        scenarios_html = scenarios_response.text
        assert "Lifecycle Test Scenario" in scenarios_html

        # Verify scenario detail page is accessible
        detail_response = test_client.get(
            f"/scenarios/{scenario_id}"
        )
        assert detail_response.status_code == 200

        # Step 4: Admin deactivates scenario
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        deactivate_response = test_client.put(
            f"/admin/scenarios/{scenario_id}",
            json={"is_active": 0},
        )
        assert deactivate_response.status_code == 200
        assert deactivate_response.json()["is_active"] == 0

        # Step 5: Teacher logs back in
        test_client.post(
            "/login",
            data={
                "username": teacher_with_group.username,
                "password": "test1234",
            },
        )

        # Step 6: Verify scenario is hidden from teachers
        scenarios_hidden_response = test_client.get(
            "/scenarios"
        )
        assert scenarios_hidden_response.status_code == 200
        scenarios_hidden_html = (
            scenarios_hidden_response.text
        )
        assert (
            "Lifecycle Test Scenario"
            not in scenarios_hidden_html
        )

        # Verify detail page is not accessible (404)
        detail_hidden_response = test_client.get(
            f"/scenarios/{scenario_id}"
        )
        assert detail_hidden_response.status_code == 404

        # Step 7: Admin reactivates scenario
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        reactivate_response = test_client.put(
            f"/admin/scenarios/{scenario_id}",
            json={"is_active": 1},
        )
        assert reactivate_response.status_code == 200
        assert (
            reactivate_response.json()["is_active"] == 1
        )

        # Step 8: Teacher verifies scenario is visible again
        test_client.post(
            "/login",
            data={
                "username": teacher_with_group.username,
                "password": "test1234",
            },
        )

        scenarios_visible_response = test_client.get(
            "/scenarios"
        )
        assert scenarios_visible_response.status_code == 200
        scenarios_visible_html = (
            scenarios_visible_response.text
        )
        assert (
            "Lifecycle Test Scenario"
            in scenarios_visible_html
        )

    def test_multiple_scenarios_filtering(
        self,
        test_client: TestClient,
        admin_user: User,
        teacher_with_group: User,
        test_framework: AnalysisFramework,
        test_student_template: PromptTemplate,
        test_group: UserGroup,
    ):
        """Test that only active scenarios are visible."""

        # Admin creates multiple scenarios with group
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Create 3 scenarios
        scenario_ids = []
        for i in range(3):
            resp = test_client.post(
                "/admin/scenarios",
                json={
                    "title": f"Scenario {i+1}",
                    "prompt": f"Prompt for scenario {i+1}",
                    "student_profile": f"Profile {i+1}",
                    "framework_id": test_framework.id,
                    "student_template_id": (
                        test_student_template.id
                    ),
                    "group_ids": [test_group.id],
                },
            )
            scenario_ids.append(resp.json()["id"])

        # Get all scenario IDs
        admin_scenarios_response = test_client.get(
            "/admin/scenarios"
        )
        assert admin_scenarios_response.status_code == 200

        # Deactivate scenario 2
        test_client.put(
            f"/admin/scenarios/{scenario_ids[1]}",
            json={"is_active": 0},
        )

        # Teacher logs in
        test_client.post(
            "/login",
            data={
                "username": teacher_with_group.username,
                "password": "test1234",
            },
        )

        # Verify only active scenarios visible
        teacher_scenarios_response = test_client.get(
            "/scenarios"
        )
        assert teacher_scenarios_response.status_code == 200
        teacher_html = teacher_scenarios_response.text

        assert "Scenario 1" in teacher_html
        assert "Scenario 2" not in teacher_html  # Inactive
        assert "Scenario 3" in teacher_html
