"""Integration tests for scenario bot configuration (Task 4).

Tests the extended POST/PUT endpoints in admin_scenarios.py to ensure
scenario-level bot configuration overrides work correctly.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.user import User


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(student_uid="bot_admin", nickname="Config Admin", role="admin")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
    """Create a test framework."""
    framework = AnalysisFramework(
        name="Bot Config Framework",
        description="For bot config testing",
        labels_json='["high", "medium", "low"]',
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


class TestScenarioBotConfigAPI:
    """Test scenario bot configuration API endpoints."""

    def test_create_scenario_with_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """POST /admin/scenarios - Create scenario with bot config overrides."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Math Scenario with GPT-4",
                "prompt": "Test math misconceptions",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "is_active": True,
                # Bot config overrides
                "chat_model": "gpt-4o",
                "chat_temperature": 0.8,
                "tutor_enabled": True,
                "tutor_intervention_threshold": 3,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Math Scenario with GPT-4"
        assert data["chat_model"] == "gpt-4o"
        assert data["chat_temperature"] == 0.8
        assert data["tutor_enabled"] == 1  # SQLite stores as int
        assert data["tutor_intervention_threshold"] == 3

    def test_create_scenario_without_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """POST /admin/scenarios - Create scenario without bot config (use globals)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Default Config Scenario",
                "prompt": "Test with default settings",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "is_active": True,
                # No bot config overrides - should use global defaults
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["chat_model"] is None
        assert data["chat_temperature"] is None
        assert data["tutor_enabled"] == 1  # Default value
        assert data["tutor_intervention_threshold"] is None

    def test_create_scenario_invalid_model_name(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """POST /admin/scenarios - Reject invalid model name."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Invalid Model Scenario",
                "prompt": "Test with invalid model",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "chat_model": "gpt-5-turbo",  # Invalid model
            },
        )

        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "chat_model" in error["loc"]

    def test_create_scenario_invalid_temperature(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """POST /admin/scenarios - Reject invalid temperature."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Invalid Temperature Scenario",
                "prompt": "Test with invalid temperature",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "chat_temperature": 3.0,  # Invalid: > 2.0
            },
        )

        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "chat_temperature" in error["loc"]

    def test_create_scenario_invalid_threshold(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """POST /admin/scenarios - Reject invalid intervention threshold."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Invalid Threshold Scenario",
                "prompt": "Test with invalid threshold",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "tutor_intervention_threshold": 15,  # Invalid: > 10
            },
        )

        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "tutor_intervention_threshold" in error["loc"]

    def test_update_scenario_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """PUT /admin/scenarios/{id} - Update scenario bot config."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Create scenario first
        create_response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Initial Scenario",
                "prompt": "Initial prompt",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "chat_model": "gpt-3.5-turbo",
                "chat_temperature": 0.5,
                "tutor_enabled": True,
                "tutor_intervention_threshold": 5,
            },
        )
        scenario_id = create_response.json()["id"]

        # Update bot config
        update_response = test_client.put(
            f"/admin/scenarios/{scenario_id}",
            json={
                "chat_model": "gpt-4o-mini",
                "chat_temperature": 1.2,
                "tutor_enabled": False,
                "tutor_intervention_threshold": 8,
            },
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["chat_model"] == "gpt-4o-mini"
        assert data["chat_temperature"] == 1.2
        assert data["tutor_enabled"] == 0  # False stored as 0
        assert data["tutor_intervention_threshold"] == 8

    def test_update_scenario_partial_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """PUT /admin/scenarios/{id} - Update only some bot config fields."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Create scenario first
        create_response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Partial Update Scenario",
                "prompt": "Initial prompt",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "chat_model": "gpt-4",
                "chat_temperature": 0.7,
                "tutor_enabled": True,
                "tutor_intervention_threshold": 5,
            },
        )
        scenario_id = create_response.json()["id"]

        # Update only temperature and threshold
        update_response = test_client.put(
            f"/admin/scenarios/{scenario_id}",
            json={
                "chat_temperature": 1.5,
                "tutor_intervention_threshold": 3,
            },
        )

        assert update_response.status_code == 200
        data = update_response.json()
        # Unchanged fields
        assert data["chat_model"] == "gpt-4"
        assert data["tutor_enabled"] == 1
        # Updated fields
        assert data["chat_temperature"] == 1.5
        assert data["tutor_intervention_threshold"] == 3

    def test_valid_model_names(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework
    ):
        """POST /admin/scenarios - Accept all valid model names."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        valid_models = [
            "gpt-3.5-turbo",
            "gpt-3.5",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4o-turbo",
            "gpt-4o",
            "gpt-4o-mini-turbo",
            "gpt-4o-mini",
        ]

        for model in valid_models:
            response = test_client.post(
                "/admin/scenarios",
                json={
                    "title": f"Scenario with {model}",
                    "prompt": "Test valid model names",
                    "student_profile": "Grade 5 student",
                    "framework_id": test_framework.id,
                    "chat_model": model,
                },
            )

            assert response.status_code == 201, f"Failed for model: {model}"
            assert response.json()["chat_model"] == model
