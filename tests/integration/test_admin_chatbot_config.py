"""Integration tests for admin chatbot configuration API."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.chatbot_config import ChatbotConfig, ChatbotConfigAudit
from src.models.user import User


class TestChatbotConfigAPI:
    """Test admin chatbot configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_config_as_admin(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test admin can retrieve chatbot configuration."""
        # Create admin user
        admin = User(
            student_uid="admin_test",
            nickname="Admin User",
            role="admin",
        )
        async_session.add(admin)
        await async_session.commit()

        # Login as admin (session-based auth)
        response = await async_client.post(
            "/login",
            data={"student_uid": "admin_test", "nickname": "Admin User"},
        )
        assert response.status_code == 200

        # Get configuration
        response = await async_client.get("/admin/chatbot-config")
        assert response.status_code == 200

        data = response.json()
        assert "student_bot" in data
        assert "tutor_bot" in data
        assert data["student_bot"]["model"] in [
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "gpt-5-mini",
            "gpt-5",
        ]
        assert 0.0 <= data["student_bot"]["temperature"] <= 2.0
        assert 50 <= data["student_bot"]["max_tokens"] <= 500

    @pytest.mark.asyncio
    async def test_get_config_as_non_admin_fails(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test non-admin cannot access chatbot configuration."""
        # Create regular user
        user = User(
            student_uid="teacher_test",
            nickname="Teacher User",
            role="teacher",
        )
        async_session.add(user)
        await async_session.commit()

        # Login as regular user
        response = await async_client.post(
            "/login",
            data={"student_uid": "teacher_test", "nickname": "Teacher User"},
        )
        assert response.status_code == 200

        # Attempt to get configuration
        response = await async_client.get("/admin/chatbot-config")
        assert response.status_code == 403
        assert "Admin role required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_config_success(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test admin can update chatbot configuration."""
        # Create admin
        admin = User(
            student_uid="admin_update",
            nickname="Admin",
            role="admin",
        )
        async_session.add(admin)
        await async_session.commit()

        # Login
        await async_client.post(
            "/login",
            data={"student_uid": "admin_update", "nickname": "Admin"},
        )

        # Update configuration
        update_data = {
            "student_bot_model": "gpt-3.5-turbo",
            "student_bot_temperature": 0.8,
            "student_bot_max_tokens": 200,
            "tutor_bot_model": "gpt-4-turbo",
            "tutor_bot_temperature": 0.4,
            "tutor_bot_max_tokens": 120,
            "tutor_bot_intervention_threshold": 5,
        }

        response = await async_client.put(
            "/admin/chatbot-config", json=update_data
        )
        assert response.status_code == 200
        assert (
            response.json()["message"]
            == "Chatbot configuration updated successfully"
        )

        # Verify in database
        result = await async_session.execute(
            select(ChatbotConfig).where(
                ChatbotConfig.config_key == "student_bot.model"
            )
        )
        config = result.scalar_one()
        assert config.config_value == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_update_config_invalid_model_fails(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test validation rejects invalid model names."""
        # Create admin
        admin = User(
            student_uid="admin_invalid",
            nickname="Admin",
            role="admin",
        )
        async_session.add(admin)
        await async_session.commit()

        # Login
        await async_client.post(
            "/login",
            data={"student_uid": "admin_invalid", "nickname": "Admin"},
        )

        # Attempt invalid update
        update_data = {
            "student_bot_model": "gpt-99-fake",  # Invalid
            "student_bot_temperature": 0.7,
            "student_bot_max_tokens": 150,
            "tutor_bot_model": "gpt-3.5-turbo",
            "tutor_bot_temperature": 0.3,
            "tutor_bot_max_tokens": 100,
            "tutor_bot_intervention_threshold": 3,
        }

        response = await async_client.put(
            "/admin/chatbot-config", json=update_data
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_update_config_invalid_temperature_fails(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test temperature range validation."""
        # Create admin
        admin = User(
            student_uid="admin_temp",
            nickname="Admin",
            role="admin",
        )
        async_session.add(admin)
        await async_session.commit()

        # Login
        await async_client.post(
            "/login", data={"student_uid": "admin_temp", "nickname": "Admin"}
        )

        # Invalid temperature (too high)
        update_data = {
            "student_bot_model": "gpt-4-turbo",
            "student_bot_temperature": 5.0,  # Invalid (max 2.0)
            "student_bot_max_tokens": 150,
            "tutor_bot_model": "gpt-3.5-turbo",
            "tutor_bot_temperature": 0.3,
            "tutor_bot_max_tokens": 100,
            "tutor_bot_intervention_threshold": 3,
        }

        response = await async_client.put(
            "/admin/chatbot-config", json=update_data
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_config_creates_audit_log(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test that config updates create audit log entries."""
        # Create admin
        admin = User(
            student_uid="admin_audit",
            nickname="Admin",
            role="admin",
        )
        async_session.add(admin)
        await async_session.commit()

        # Login
        await async_client.post(
            "/login",
            data={"student_uid": "admin_audit", "nickname": "Admin"},
        )

        # Update config
        update_data = {
            "student_bot_model": "gpt-3.5-turbo",
            "student_bot_temperature": 0.9,
            "student_bot_max_tokens": 175,
            "tutor_bot_model": "gpt-4-turbo",
            "tutor_bot_temperature": 0.5,
            "tutor_bot_max_tokens": 110,
            "tutor_bot_intervention_threshold": 4,
        }

        await async_client.put("/admin/chatbot-config", json=update_data)

        # Verify audit log entries exist
        result = await async_session.execute(
            select(ChatbotConfigAudit).where(
                ChatbotConfigAudit.changed_by == admin.id
            )
        )
        audit_logs = result.scalars().all()

        assert len(audit_logs) > 0
        assert any(
            log.config_key == "student_bot.model" for log in audit_logs
        )
        assert any(log.new_value == "gpt-3.5-turbo" for log in audit_logs)

    @pytest.mark.asyncio
    async def test_reset_to_defaults(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test reset endpoint restores factory defaults."""
        # Create admin
        admin = User(
            student_uid="admin_reset", nickname="Admin", role="admin"
        )
        async_session.add(admin)
        await async_session.commit()

        # Login
        await async_client.post(
            "/login", data={"student_uid": "admin_reset", "nickname": "Admin"}
        )

        # First, change config
        update_data = {
            "student_bot_model": "gpt-3.5-turbo",
            "student_bot_temperature": 0.9,
            "student_bot_max_tokens": 200,
            "tutor_bot_model": "gpt-4-turbo",
            "tutor_bot_temperature": 0.5,
            "tutor_bot_max_tokens": 120,
            "tutor_bot_intervention_threshold": 7,
        }
        await async_client.put("/admin/chatbot-config", json=update_data)

        # Reset to defaults
        response = await async_client.post("/admin/chatbot-config/reset")
        assert response.status_code == 200

        data = response.json()
        assert data["message"] == "Configuration reset to defaults"
        assert data["defaults"]["student_bot"]["model"] == "gpt-4-turbo"
        assert (
            data["defaults"]["student_bot"]["temperature"] == 0.7
        )
        assert data["defaults"]["student_bot"]["max_tokens"] == 150

        # Verify in database
        result = await async_session.execute(
            select(ChatbotConfig).where(
                ChatbotConfig.config_key == "student_bot.model"
            )
        )
        config = result.scalar_one()
        assert config.config_value == "gpt-4-turbo"

    @pytest.mark.asyncio
    async def test_cost_metrics_endpoint(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test cost metrics endpoint (Phase 3 placeholder)."""
        # Create admin
        admin = User(
            student_uid="admin_cost", nickname="Admin", role="admin"
        )
        async_session.add(admin)
        await async_session.commit()

        # Login
        await async_client.post(
            "/login", data={"student_uid": "admin_cost", "nickname": "Admin"}
        )

        # Get cost metrics
        response = await async_client.get("/admin/chatbot-config/costs")
        assert response.status_code == 200

        data = response.json()
        # Phase 3 placeholder returns message
        assert "placeholder" in data

    @pytest.mark.asyncio
    async def test_settings_page_renders(
        self, async_client: AsyncClient, async_session: AsyncSession
    ):
        """Test chatbot settings page renders for admin."""
        # Create admin
        admin = User(
            student_uid="admin_page", nickname="Admin", role="admin"
        )
        async_session.add(admin)
        await async_session.commit()

        # Login
        await async_client.post(
            "/login", data={"student_uid": "admin_page", "nickname": "Admin"}
        )

        # Get settings page
        response = await async_client.get(
            "/admin/chatbot-config/settings"
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Chatbot Configuration" in response.content
