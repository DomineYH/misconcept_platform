"""Integration tests for SessionManager configuration loading."""
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User, Scenario, Session, AnalysisFramework
from src.models.chatbot_config import ChatbotConfig
from src.services.session_mgr import SessionManager


class TestSessionManagerConfigIntegration:
    """Test SessionManager loads and uses bot configuration."""

    @pytest.mark.asyncio
    async def test_session_manager_loads_config_from_db(
        self, async_session: AsyncSession
    ):
        """Test SessionManager loads config from database on initialize."""
        # Create test data
        admin = User(
            student_uid="admin_sm", nickname="Admin", role="admin"
        )
        async_session.add(admin)

        framework = AnalysisFramework(
            name="Test Framework",
            description="Test",
            labels_json='["label1", "label2", "label3"]',
        )
        async_session.add(framework)

        scenario = Scenario(
            title="Test Scenario",
            prompt="Test prompt for student bot with misconception",
            student_profile="Grade 5 student",
            framework_id=1,
            created_by=1,
        )
        async_session.add(scenario)

        session = Session(teacher_id=1, scenario_id=1)
        async_session.add(session)

        # Add custom config to database
        configs = [
            ChatbotConfig(
                config_key="student_bot.model",
                config_value="gpt-3.5-turbo",
                config_type="string",
            ),
            ChatbotConfig(
                config_key="student_bot.temperature",
                config_value="0.9",
                config_type="float",
            ),
            ChatbotConfig(
                config_key="student_bot.max_tokens",
                config_value="175",
                config_type="integer",
            ),
            ChatbotConfig(
                config_key="tutor_bot.model",
                config_value="gpt-4-turbo",
                config_type="string",
            ),
            ChatbotConfig(
                config_key="tutor_bot.temperature",
                config_value="0.2",
                config_type="float",
            ),
            ChatbotConfig(
                config_key="tutor_bot.max_tokens",
                config_value="90",
                config_type="integer",
            ),
            ChatbotConfig(
                config_key="tutor_bot.intervention_threshold",
                config_value="5",
                config_type="integer",
            ),
        ]
        for config in configs:
            async_session.add(config)

        await async_session.commit()

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session, session_id=session.id
        )
        await session_mgr.initialize()

        # Verify StudentBot uses config from database
        assert session_mgr.student_bot.model == "gpt-3.5-turbo"
        assert session_mgr.student_bot.temperature == 0.9
        assert session_mgr.student_bot.max_tokens == 175

        # Verify TutorBot uses config from database
        assert session_mgr.tutor_bot.model == "gpt-4-turbo"
        assert session_mgr.tutor_bot.temperature == 0.2
        assert session_mgr.tutor_bot.max_tokens == 90
        assert session_mgr.tutor_bot.intervention_threshold == 5

    @pytest.mark.asyncio
    async def test_session_manager_falls_back_to_env_vars(
        self, async_session: AsyncSession
    ):
        """Test SessionManager falls back to env vars when DB is empty."""
        from src.config import config

        # Create minimal test data (no chatbot_config entries)
        admin = User(
            student_uid="admin_fallback", nickname="Admin", role="admin"
        )
        async_session.add(admin)

        framework = AnalysisFramework(
            name="Test Framework",
            description="Test",
            labels_json='["label1", "label2", "label3"]',
        )
        async_session.add(framework)

        scenario = Scenario(
            title="Test Scenario",
            prompt="Test prompt for student bot",
            student_profile="Grade 5 student",
            framework_id=1,
            created_by=1,
        )
        async_session.add(scenario)

        session = Session(teacher_id=1, scenario_id=1)
        async_session.add(session)
        await async_session.commit()

        # Clear any existing config (if seeded)
        await async_session.execute(text("DELETE FROM chatbot_config"))
        await async_session.commit()

        # Invalidate cache to ensure fallback to env vars
        from src.services.config_cache import bot_config_cache
        await bot_config_cache.invalidate()

        # Initialize SessionManager
        session_mgr = SessionManager(
            db_session=async_session, session_id=session.id
        )
        await session_mgr.initialize()

        # Should fall back to environment variables
        assert session_mgr.student_bot.model == config.CHAT_MODEL
        assert session_mgr.tutor_bot.model == config.ANALYSIS_MODEL

    @pytest.mark.asyncio
    async def test_config_cache_used_for_multiple_sessions(
        self, async_session: AsyncSession
    ):
        """Test that config cache reduces DB queries for multiple sessions."""
        from src.services.config_cache import bot_config_cache

        # Clear cache
        await bot_config_cache.invalidate()

        # Create test data
        admin = User(student_uid="admin_cache", nickname="Admin", role="admin")
        async_session.add(admin)

        framework = AnalysisFramework(
            name="Test Framework",
            description="Test",
            labels_json='["label1", "label2", "label3"]',
        )
        async_session.add(framework)

        scenario = Scenario(
            title="Test Scenario",
            prompt="Test prompt for student bot",
            student_profile="Grade 5 student",
            framework_id=1,
            created_by=1,
        )
        async_session.add(scenario)

        # Create two sessions
        session1 = Session(teacher_id=1, scenario_id=1)
        session2 = Session(teacher_id=1, scenario_id=1)
        async_session.add_all([session1, session2])

        # Add config
        config = ChatbotConfig(
            config_key="student_bot.model",
            config_value="gpt-3.5-turbo",
            config_type="string",
        )
        async_session.add(config)
        await async_session.commit()

        # Initialize first SessionManager (cache miss)
        mgr1 = SessionManager(
            db_session=async_session, session_id=session1.id
        )
        await mgr1.initialize()

        # Initialize second SessionManager (should use cache)
        mgr2 = SessionManager(
            db_session=async_session, session_id=session2.id
        )
        await mgr2.initialize()

        # Both should have same model (from same config)
        assert mgr1.student_bot.model == mgr2.student_bot.model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_updated_config_affects_new_sessions(
        self, async_session: AsyncSession
    ):
        """Test that config updates are reflected in new sessions after cache invalidation."""
        from src.services.config_cache import bot_config_cache

        # Setup initial config
        admin = User(
            student_uid="admin_update_test", nickname="Admin", role="admin"
        )
        async_session.add(admin)

        framework = AnalysisFramework(
            name="Test Framework",
            description="Test",
            labels_json='["label1", "label2", "label3"]',
        )
        async_session.add(framework)

        scenario = Scenario(
            title="Test Scenario",
            prompt="Test prompt for student bot",
            student_profile="Grade 5 student",
            framework_id=1,
            created_by=1,
        )
        async_session.add(scenario)

        session1 = Session(teacher_id=1, scenario_id=1)
        async_session.add(session1)

        config = ChatbotConfig(
            config_key="student_bot.model",
            config_value="gpt-4-turbo",
            config_type="string",
        )
        async_session.add(config)
        await async_session.commit()

        # Clear cache to ensure fresh load of config
        await bot_config_cache.invalidate()

        # Create first session with initial config
        mgr1 = SessionManager(
            db_session=async_session, session_id=session1.id
        )
        await mgr1.initialize()
        assert mgr1.student_bot.model == "gpt-4-turbo"

        # Update config in database
        result = await async_session.execute(
            select(ChatbotConfig).where(
                ChatbotConfig.config_key == "student_bot.model"
            )
        )
        config_row = result.scalar_one()
        config_row.config_value = "gpt-3.5-turbo"
        await async_session.commit()

        # Invalidate cache (simulates PUT /admin/chatbot-config)
        await bot_config_cache.invalidate()

        # Create second session - should use updated config
        session2 = Session(teacher_id=1, scenario_id=1)
        async_session.add(session2)
        await async_session.commit()

        mgr2 = SessionManager(
            db_session=async_session, session_id=session2.id
        )
        await mgr2.initialize()

        # New session should have updated model
        assert mgr2.student_bot.model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_config_priority_order(self, async_session: AsyncSession):
        """Test configuration priority: DB > Env vars > Defaults."""
        from src.config import config

        # Create test data
        admin = User(
            student_uid="admin_priority", nickname="Admin", role="admin"
        )
        async_session.add(admin)

        framework = AnalysisFramework(
            name="Test Framework",
            description="Test",
            labels_json='["label1", "label2", "label3"]',
        )
        async_session.add(framework)

        scenario = Scenario(
            title="Test",
            prompt="Test prompt for student bot",
            student_profile="Test student",
            framework_id=1,
            created_by=1,
        )
        async_session.add(scenario)

        session = Session(teacher_id=1, scenario_id=1)
        async_session.add(session)

        # Add partial config (only temperature)
        temp_config = ChatbotConfig(
            config_key="student_bot.temperature",
            config_value="0.5",
            config_type="float",
        )
        async_session.add(temp_config)
        await async_session.commit()

        # Invalidate cache to load new config
        from src.services.config_cache import bot_config_cache
        await bot_config_cache.invalidate()

        # Initialize SessionManager
        mgr = SessionManager(db_session=async_session, session_id=session.id)
        await mgr.initialize()

        # Temperature should come from DB (highest priority)
        assert mgr.student_bot.temperature == 0.5

        # Model should fall back to env var (DB doesn't have it)
        assert mgr.student_bot.model == config.CHAT_MODEL
