"""Integration tests for scenario bot configuration (Task 4).

Tests the extended POST/PUT endpoints in admin_scenarios.py to ensure
scenario-level bot configuration overrides work correctly.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.user import User


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(username="bot_admin", nickname="Config Admin", role="admin")
    user.set_password("test1234")
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


@pytest.fixture
async def test_student_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test student template."""
    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text="You are a test student bot. Scenario: {scenario_title}. Profile: {student_profile}. Context: {prompt}",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_tutor_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test tutor template."""
    template = PromptTemplate(
        bot_type="tutor",
        template_name="Test Tutor Template",
        version=1,
        template_text="You are a test tutor bot. Scenario: {scenario_title}. Profile: {student_profile}. Context: {prompt}",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


class TestScenarioBotConfigAPI:
    """Test scenario bot configuration API endpoints."""

    def test_create_scenario_with_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate, test_tutor_template: PromptTemplate
    ):
        """POST /admin/scenarios - Create scenario with bot config overrides."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
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
                # Template-based config
                "student_template_id": test_student_template.id,
                "tutor_template_id": test_tutor_template.id,
                # Bot config overrides
                "chat_model": "gpt-4o",
                "chat_temperature": 0.8,
                "tutor_intervention_threshold": 3,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Math Scenario with GPT-4"
        assert data["student_template_id"] == test_student_template.id
        assert data["tutor_template_id"] == test_tutor_template.id
        assert data["chat_model"] == "gpt-4o"
        assert data["chat_temperature"] == 0.8
        assert data["tutor_template_id"] is not None
        assert data["tutor_intervention_threshold"] == 3

    def test_create_scenario_without_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate
    ):
        """POST /admin/scenarios - Create scenario without tutor (student only)."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
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
                "student_template_id": test_student_template.id,
                # No tutor_template_id - tutor disabled
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["student_template_id"] == test_student_template.id
        assert data["tutor_template_id"] is None
        # Schema defaults are applied when not provided
        assert data["chat_model"] == "gpt-4-turbo"
        assert data["chat_temperature"] == 0.7
        assert data["tutor_intervention_threshold"] == 3

    def test_create_scenario_invalid_model_name(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate
    ):
        """POST /admin/scenarios - Reject invalid model name."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Invalid Model Scenario",
                "prompt": "Test with invalid model",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "student_template_id": test_student_template.id,
                "chat_model": "gpt-5-turbo",  # Invalid model
            },
        )

        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "chat_model" in error["loc"]

    def test_create_scenario_invalid_temperature(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate
    ):
        """POST /admin/scenarios - Reject invalid temperature."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Invalid Temperature Scenario",
                "prompt": "Test with invalid temperature",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "student_template_id": test_student_template.id,
                "chat_temperature": 3.0,  # Invalid: > 2.0
            },
        )

        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "chat_temperature" in error["loc"]

    def test_create_scenario_invalid_threshold(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate
    ):
        """POST /admin/scenarios - Reject invalid intervention threshold."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        response = test_client.post(
            "/admin/scenarios",
            json={
                "title": "Invalid Threshold Scenario",
                "prompt": "Test with invalid threshold",
                "student_profile": "Grade 5 student",
                "framework_id": test_framework.id,
                "student_template_id": test_student_template.id,
                "tutor_intervention_threshold": 15,  # Invalid: > 10
            },
        )

        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "tutor_intervention_threshold" in error["loc"]

    def test_update_scenario_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate, test_tutor_template: PromptTemplate
    ):
        """PUT /admin/scenarios/{id} - Update scenario bot config."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
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
                "student_template_id": test_student_template.id,
                "tutor_template_id": test_tutor_template.id,
                "chat_model": "gpt-4-turbo",
                "chat_temperature": 0.5,
                "tutor_intervention_threshold": 5,
            },
        )
        scenario_id = create_response.json()["id"]

        # Update bot config (disable tutor)
        update_response = test_client.put(
            f"/admin/scenarios/{scenario_id}",
            json={
                "chat_model": "gpt-4o-mini",
                "chat_temperature": 1.2,
                "tutor_template_id": -1,  # Disable tutor
                "tutor_intervention_threshold": 8,
            },
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["chat_model"] == "gpt-4o-mini"
        assert data["chat_temperature"] == 1.2
        assert data["tutor_template_id"] is None  # Tutor disabled
        assert data["tutor_intervention_threshold"] == 8

    def test_update_scenario_partial_bot_config(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate, test_tutor_template: PromptTemplate
    ):
        """PUT /admin/scenarios/{id} - Update only some bot config fields."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
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
                "student_template_id": test_student_template.id,
                "tutor_template_id": test_tutor_template.id,
                "chat_model": "gpt-4",
                "chat_temperature": 0.7,
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
        assert data["tutor_template_id"] is not None
        # Updated fields
        assert data["chat_temperature"] == 1.5
        assert data["tutor_intervention_threshold"] == 3

    def test_valid_model_names(
        self, test_client: TestClient, admin_user: User, test_framework: AnalysisFramework,
        test_student_template: PromptTemplate
    ):
        """POST /admin/scenarios - Accept all valid model names."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "username": admin_user.username,
                "password": "test1234",
            },
        )

        # Only Responses API compatible models (GPT-3.5 not supported)
        valid_models = [
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4o-turbo",
            "gpt-4o",
            "gpt-4o-mini-turbo",
            "gpt-4o-mini",
            "gpt-5.1-chat-latest",
            "gpt-5.1",
            "gpt-5",
        ]

        for model in valid_models:
            response = test_client.post(
                "/admin/scenarios",
                json={
                    "title": f"Scenario with {model}",
                    "prompt": "Test valid model names",
                    "student_profile": "Grade 5 student",
                    "framework_id": test_framework.id,
                    "student_template_id": test_student_template.id,
                    "chat_model": model,
                },
            )

            assert response.status_code == 201, f"Failed for model: {model}"
            assert response.json()["chat_model"] == model
