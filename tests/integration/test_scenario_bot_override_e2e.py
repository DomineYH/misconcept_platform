"""
Integration tests for Phase 2: Scenario-specific bot configuration override.

Tests end-to-end functionality from API to SessionManager to actual bot initialization.
This ensures the full stack (API → DB → SessionManager → Bot) works correctly.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.scenario import Scenario
from src.models.session import Session as DialogueSession
from src.models.user import User
from src.models.analysis_framework import AnalysisFramework
from src.models.chatbot_config import ChatbotConfig
from src.services.session_mgr import SessionManager


@pytest.fixture
async def admin_user(async_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(student_uid="admin", nickname="Administrator", role="admin")
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.fixture
async def framework(async_session: AsyncSession) -> AnalysisFramework:
    """Create a test framework."""
    framework = AnalysisFramework(
        name="Test Framework",
        description="For E2E testing",
        labels_json='["high", "medium", "low"]',
    )
    async_session.add(framework)
    await async_session.commit()
    await async_session.refresh(framework)
    return framework


@pytest.fixture
async def chatbot_config(async_session: AsyncSession) -> dict:
    """Create global chatbot configuration entries.

    Returns a dict with expected global config values for assertion.
    """
    # Check if configs already exist (from other tests in same session)
    result = await async_session.execute(
        select(ChatbotConfig).where(
            ChatbotConfig.config_key == "student_bot.model"
        )
    )
    existing = result.scalar_one_or_none()

    if not existing:
        # Only create if they don't exist yet
        configs = [
            ChatbotConfig(
                config_key="student_bot.model",
                config_value="gpt-3.5-turbo",
                config_type="string",
                description="Global default model",
            ),
            ChatbotConfig(
                config_key="student_bot.temperature",
                config_value="0.7",
                config_type="float",
                description="Global default temperature",
            ),
            ChatbotConfig(
                config_key="student_bot.max_tokens",
                config_value="150",
                config_type="integer",
                description="Global default max tokens",
            ),
            ChatbotConfig(
                config_key="tutor_bot.model",
                config_value="gpt-4o-mini",
                config_type="string",
                description="Global tutor model",
            ),
            ChatbotConfig(
                config_key="tutor_bot.temperature",
                config_value="0.3",
                config_type="float",
                description="Global tutor temperature",
            ),
            ChatbotConfig(
                config_key="tutor_bot.max_tokens",
                config_value="100",
                config_type="integer",
                description="Global tutor max tokens",
            ),
            ChatbotConfig(
                config_key="tutor_bot.intervention_threshold",
                config_value="3",
                config_type="integer",
                description="Global intervention threshold",
            ),
        ]
        for config in configs:
            async_session.add(config)
        await async_session.commit()

    return {
        "student_model": "gpt-3.5-turbo",
        "student_temperature": 0.7,
        "tutor_threshold": 3,
    }


class TestScenarioBotConfigE2E:
    """End-to-end tests for scenario bot configuration override."""

    @pytest.mark.asyncio
    async def test_create_scenario_with_custom_bot_config(
        self, async_client: AsyncClient, admin_user, framework
    ):
        """Test creating a scenario with custom bot configuration via API."""
        # Login as admin
        await async_client.post("/login", data={
            "student_uid": "admin",
            "nickname": "Administrator",
        })

        # Create scenario with bot config
        payload = {
            "title": "Advanced Physics (GPT-4o)",
            "prompt": "Student believes force equals mass times velocity (F=mv)",
            "student_profile": "Grade 10 physics student",
            "framework_id": framework.id,
            "is_active": True,
            # Bot configuration overrides
            "chat_model": "gpt-4o",
            "chat_temperature": 0.9,
            "tutor_enabled": True,
            "tutor_intervention_threshold": 5,
        }

        response = await async_client.post("/admin/scenarios", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["chat_model"] == "gpt-4o"
        assert data["chat_temperature"] == 0.9
        assert data["tutor_enabled"] == 1  # SQLite stores as int
        assert data["tutor_intervention_threshold"] == 5

    @pytest.mark.asyncio
    async def test_scenario_overrides_global_config(
        self, async_session: AsyncSession, admin_user, framework, chatbot_config
    ):
        """Test that scenario config overrides global chatbot_config."""
        # Create scenario with model override
        scenario = Scenario(
            title="Custom Model Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
            chat_model="gpt-4o",  # Override global gpt-3.5-turbo
            chat_temperature=0.5,  # Override global 0.7
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Create dialogue session
        dialogue_session = DialogueSession(
            teacher_id=admin_user.id,
            scenario_id=scenario.id,
        )
        async_session.add(dialogue_session)
        await async_session.commit()
        await async_session.refresh(dialogue_session)

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session,
            session_id=dialogue_session.id,
        )
        await session_mgr.initialize()

        # Verify StudentBot uses scenario overrides
        assert session_mgr.student_bot.model == "gpt-4o"
        assert session_mgr.student_bot.temperature == 0.5

    @pytest.mark.asyncio
    async def test_tutor_disabled_for_scenario(
        self, async_session: AsyncSession, admin_user, framework
    ):
        """Test that TutorBot is not initialized when tutor_enabled=False."""
        # Create scenario with TutorBot disabled
        scenario = Scenario(
            title="Self-Study Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
            tutor_enabled=False,  # Disable TutorBot
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Create dialogue session
        dialogue_session = DialogueSession(
            teacher_id=admin_user.id,
            scenario_id=scenario.id,
        )
        async_session.add(dialogue_session)
        await async_session.commit()
        await async_session.refresh(dialogue_session)

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session,
            session_id=dialogue_session.id,
        )
        await session_mgr.initialize()

        # Verify TutorBot is None
        assert session_mgr.tutor_bot is None

    @pytest.mark.asyncio
    async def test_scenario_falls_back_to_global_when_null(
        self, async_session: AsyncSession, admin_user, framework, chatbot_config
    ):
        """Test that NULL scenario fields fall back to global config."""
        # Create scenario WITHOUT bot config overrides
        scenario = Scenario(
            title="Default Config Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
            # All bot config fields are NULL (except tutor_enabled which has default=True)
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Create dialogue session
        dialogue_session = DialogueSession(
            teacher_id=admin_user.id,
            scenario_id=scenario.id,
        )
        async_session.add(dialogue_session)
        await async_session.commit()
        await async_session.refresh(dialogue_session)

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session,
            session_id=dialogue_session.id,
        )
        await session_mgr.initialize()

        # Verify uses global config (from chatbot_config fixture)
        assert session_mgr.student_bot.model == chatbot_config["student_model"]
        assert session_mgr.student_bot.temperature == chatbot_config["student_temperature"]
        assert session_mgr.tutor_bot is not None  # tutor_enabled defaults to True
        assert session_mgr.tutor_bot.intervention_threshold == chatbot_config["tutor_threshold"]

    @pytest.mark.asyncio
    async def test_update_scenario_bot_config_via_api(
        self, async_client: AsyncClient, async_session: AsyncSession,
        admin_user, framework
    ):
        """Test updating scenario bot configuration via PUT endpoint."""
        # Create scenario
        scenario = Scenario(
            title="Initial Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Login as admin
        await async_client.post("/login", data={
            "student_uid": "admin",
            "nickname": "Administrator",
        })

        # Update scenario with bot config
        update_payload = {
            "chat_model": "gpt-4o-mini",
            "tutor_enabled": False,
        }

        response = await async_client.put(
            f"/admin/scenarios/{scenario.id}",
            json=update_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["chat_model"] == "gpt-4o-mini"
        assert data["tutor_enabled"] == 0  # False stored as 0

        # Verify in database
        await async_session.refresh(scenario)
        assert scenario.chat_model == "gpt-4o-mini"
        assert scenario.tutor_enabled is False

    @pytest.mark.asyncio
    async def test_temperature_zero_handled_correctly(
        self, async_session: AsyncSession, admin_user, framework
    ):
        """Test that temperature=0.0 (falsy value) is handled correctly."""
        # Create scenario with temperature=0.0 (deterministic responses)
        scenario = Scenario(
            title="Deterministic Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
            chat_temperature=0.0,  # Explicitly 0.0
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Create dialogue session
        dialogue_session = DialogueSession(
            teacher_id=admin_user.id,
            scenario_id=scenario.id,
        )
        async_session.add(dialogue_session)
        await async_session.commit()
        await async_session.refresh(dialogue_session)

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session,
            session_id=dialogue_session.id,
        )
        await session_mgr.initialize()

        # Verify temperature is exactly 0.0 (not global default)
        assert session_mgr.student_bot.temperature == 0.0

    @pytest.mark.asyncio
    async def test_config_priority_order(
        self, async_session: AsyncSession, admin_user, framework, chatbot_config
    ):
        """Test configuration priority: Scenario > Global DB > Env > Default."""
        # This test verifies the full priority chain
        # Scenario override should take precedence over all others

        scenario = Scenario(
            title="Priority Test Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
            chat_model="gpt-4o",  # Scenario override (highest priority)
            tutor_intervention_threshold=7,  # Scenario override
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Create dialogue session
        dialogue_session = DialogueSession(
            teacher_id=admin_user.id,
            scenario_id=scenario.id,
        )
        async_session.add(dialogue_session)
        await async_session.commit()
        await async_session.refresh(dialogue_session)

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session,
            session_id=dialogue_session.id,
        )
        await session_mgr.initialize()

        # Verify priority order
        assert session_mgr.student_bot.model == "gpt-4o"  # Scenario override
        assert session_mgr.tutor_bot.intervention_threshold == 7  # Scenario override
        # temperature should use global default (not overridden)
        assert session_mgr.student_bot.temperature == chatbot_config["student_temperature"]

    @pytest.mark.asyncio
    async def test_invalid_bot_config_rejected_by_api(
        self, async_client: AsyncClient, admin_user, framework
    ):
        """Test that API rejects invalid bot configuration values."""
        # Login as admin
        await async_client.post("/login", data={
            "student_uid": "admin",
            "nickname": "Administrator",
        })

        # Try to create scenario with invalid temperature (>2.0)
        invalid_payload = {
            "title": "Invalid Config Scenario",
            "prompt": "Test prompt",
            "student_profile": "Grade 5",
            "framework_id": framework.id,
            "chat_temperature": 5.0,  # Invalid (>2.0)
        }

        response = await async_client.post("/admin/scenarios", json=invalid_payload)

        assert response.status_code == 422  # Validation error

        # Try with invalid model name
        invalid_payload2 = {
            "title": "Invalid Model Scenario",
            "prompt": "Test prompt",
            "student_profile": "Grade 5",
            "framework_id": framework.id,
            "chat_model": "gpt-99-fake",  # Invalid model
        }

        response2 = await async_client.post("/admin/scenarios", json=invalid_payload2)

        assert response2.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_tutor_intervention_threshold_override(
        self, async_session: AsyncSession, admin_user, framework, chatbot_config
    ):
        """Test that tutor intervention threshold override works correctly."""
        # Create scenario with custom intervention threshold
        scenario = Scenario(
            title="Custom Threshold Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
            tutor_intervention_threshold=8,  # Override global 3
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Create dialogue session
        dialogue_session = DialogueSession(
            teacher_id=admin_user.id,
            scenario_id=scenario.id,
        )
        async_session.add(dialogue_session)
        await async_session.commit()
        await async_session.refresh(dialogue_session)

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session,
            session_id=dialogue_session.id,
        )
        await session_mgr.initialize()

        # Verify TutorBot uses scenario override
        assert session_mgr.tutor_bot.intervention_threshold == 8
        # Other tutor config should use global defaults
        assert session_mgr.tutor_bot.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_mixed_scenario_and_global_config(
        self, async_session: AsyncSession, admin_user, framework, chatbot_config
    ):
        """Test scenario with partial overrides uses mix of scenario and global config."""
        # Create scenario with only model override (other fields NULL)
        scenario = Scenario(
            title="Mixed Config Scenario",
            prompt="Test prompt",
            student_profile="Grade 5",
            framework_id=framework.id,
            created_by=admin_user.id,
            chat_model="gpt-4o-mini",  # Override only model
            # chat_temperature is NULL (use global)
            # tutor_intervention_threshold is NULL (use global)
        )
        async_session.add(scenario)
        await async_session.commit()
        await async_session.refresh(scenario)

        # Create dialogue session
        dialogue_session = DialogueSession(
            teacher_id=admin_user.id,
            scenario_id=scenario.id,
        )
        async_session.add(dialogue_session)
        await async_session.commit()
        await async_session.refresh(dialogue_session)

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session,
            session_id=dialogue_session.id,
        )
        await session_mgr.initialize()

        # Verify mixed configuration
        assert session_mgr.student_bot.model == "gpt-4o-mini"  # Scenario override
        assert session_mgr.student_bot.temperature == chatbot_config["student_temperature"]  # Global
        assert session_mgr.tutor_bot.intervention_threshold == chatbot_config["tutor_threshold"]  # Global
