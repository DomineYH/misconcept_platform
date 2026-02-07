"""Integration tests for HTML response from send_message endpoint.

Tests that POST /sessions/{id}/messages returns HTML instead of JSON,
which was causing the 2-second polling delay (FIX-001).
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User, AnalysisFramework, Scenario, Session
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create test user."""
    user = User(
        username="test_html_user_001",
        nickname="HTML테스트사용자",
        role="teacher",
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_session(
    db_session: AsyncSession,
    test_user: User,
    test_scenario: Scenario,
) -> Session:
    """Create test session."""
    session = Session(
        teacher_id=test_user.id,
        scenario_id=test_scenario.id,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


class TestSendMessageReturnsHTML:
    """Test that send_message endpoint returns HTML instead of JSON."""

    @patch("src.api.routes.session_messages.SessionManager")
    async def test_send_message_returns_html(
        self,
        mock_session_manager,
        test_client: TestClient,
        db_session: AsyncSession,
        test_session: Session,
        test_user: User,
    ):
        """Test that POST /sessions/{id}/messages returns HTML."""
        # Create proper mock message with role attribute
        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = test_session.id
        mock_msg.role = "teacher"
        mock_msg.content = "Test message"
        mock_msg.created_at = datetime(2025, 1, 1, 0, 0, 0)

        # Mock SessionManager to avoid OpenAI API calls
        mock_manager_instance = AsyncMock()
        mock_manager_instance.process_teacher_message.return_value = [mock_msg]
        mock_session_manager.return_value = mock_manager_instance

        # Login as test user
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Send message
        response = test_client.post(
            f"/sessions/{test_session.id}/messages",
            data={"content": "Test message"},
            cookies=cookies,
        )

        # Verify response
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("src.api.routes.session_messages.SessionManager")
    async def test_send_message_html_structure(
        self,
        mock_session_manager,
        test_client: TestClient,
        db_session: AsyncSession,
        test_session: Session,
        test_user: User,
    ):
        """Test HTML structure of send_message response."""
        # Create proper mock message with role attribute
        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = test_session.id
        mock_msg.role = "teacher"
        mock_msg.content = "Test message content"
        mock_msg.created_at = datetime(2025, 1, 1, 0, 0, 0)

        # Mock SessionManager
        mock_manager_instance = AsyncMock()
        mock_manager_instance.process_teacher_message.return_value = [mock_msg]
        mock_session_manager.return_value = mock_manager_instance

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Send message
        response = test_client.post(
            f"/sessions/{test_session.id}/messages",
            data={"content": "Test message content"},
            cookies=cookies,
        )

        html = response.text

        # Verify HTML contains message elements
        assert '<div class="message' in html
        assert 'data-message-id=' in html
        assert "Test message content" in html

    @patch("src.api.routes.session_messages.SessionManager")
    async def test_send_message_content_correctness(
        self,
        mock_session_manager,
        test_client: TestClient,
        db_session: AsyncSession,
        test_session: Session,
        test_user: User,
    ):
        """Test that message content is correctly included in HTML."""
        test_content = "Hello, this is a test message"

        # Create proper mock message with role attribute
        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = test_session.id
        mock_msg.role = "teacher"
        mock_msg.content = test_content
        mock_msg.created_at = datetime(2025, 1, 1, 0, 0, 0)

        # Mock SessionManager
        mock_manager_instance = AsyncMock()
        mock_manager_instance.process_teacher_message.return_value = [mock_msg]
        mock_session_manager.return_value = mock_manager_instance

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Send message
        response = test_client.post(
            f"/sessions/{test_session.id}/messages",
            data={"content": test_content},
            cookies=cookies,
        )

        # Verify content
        assert response.status_code == 200
        assert test_content in response.text

    async def test_send_message_error_handling(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test error handling for invalid session."""
        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Try to send message to non-existent session
        response = test_client.post(
            "/sessions/99999/messages",  # Non-existent session
            data={"content": "Test"},
            cookies=cookies,
        )

        # Should return 404
        assert response.status_code == 404


class TestSendMessageValidation:
    """Test message validation in send_message endpoint."""

    async def test_empty_content_rejected(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_session: Session,
        test_user: User,
    ):
        """Test that empty message content is rejected."""
        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Send empty message
        response = test_client.post(
            f"/sessions/{test_session.id}/messages",
            data={"content": ""},
            cookies=cookies,
        )

        # Should return 400
        assert response.status_code in [400, 422]

    async def test_forbidden_access_other_user_session(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_session: Session,
    ):
        """Test that users cannot send messages to other users' sessions."""
        # Create another user
        other_user = User(
            username="other_user_001",
            nickname="다른사용자",
            role="teacher",
        )
        other_user.set_password("test1234")
        db_session.add(other_user)
        await db_session.commit()

        # Login as other user
        login_response = test_client.post(
            "/login",
            data={
                "username": other_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Try to send message to test_session (owned by test_user)
        response = test_client.post(
            f"/sessions/{test_session.id}/messages",
            data={"content": "Test message"},
            cookies=cookies,
        )

        # Should return 403
        assert response.status_code == 403


class TestMultipleMessagesHTML:
    """Test HTML rendering for multiple messages."""

    @patch("src.api.routes.session_messages.SessionManager")
    async def test_multiple_messages_rendered(
        self,
        mock_session_manager,
        test_client: TestClient,
        db_session: AsyncSession,
        test_session: Session,
        test_user: User,
    ):
        """Test that multiple messages are all rendered in HTML."""
        # Create proper mock message objects with role attribute
        teacher_msg = AsyncMock()
        teacher_msg.id = 1
        teacher_msg.session_id = test_session.id
        teacher_msg.role = "teacher"
        teacher_msg.content = "Teacher message"
        teacher_msg.created_at = datetime(2025, 1, 1, 0, 0, 0)

        student_msg = AsyncMock()
        student_msg.id = 2
        student_msg.session_id = test_session.id
        student_msg.role = "student"
        student_msg.content = "Student response"
        student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

        tutor_msg = AsyncMock()
        tutor_msg.id = 3
        tutor_msg.session_id = test_session.id
        tutor_msg.role = "tutor"
        tutor_msg.content = "Tutor intervention"
        tutor_msg.created_at = datetime(2025, 1, 1, 0, 0, 2)

        # Mock SessionManager to return multiple messages
        mock_manager_instance = AsyncMock()
        mock_manager_instance.process_teacher_message.return_value = [
            teacher_msg,
            student_msg,
            tutor_msg,
        ]
        mock_session_manager.return_value = mock_manager_instance

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Send message
        response = test_client.post(
            f"/sessions/{test_session.id}/messages",
            data={"content": "Teacher message"},
            cookies=cookies,
        )

        html = response.text

        # Verify all messages are in HTML
        assert response.status_code == 200
        assert "Teacher message" in html
        assert "Student response" in html
        assert "Tutor intervention" in html

        # Verify message structure for each sender type
        assert 'class="message message-teacher"' in html
        assert 'class="message message-student"' in html
        assert 'class="message message-tutor"' in html
