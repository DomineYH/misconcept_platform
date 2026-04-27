"""Unit tests for message updates endpoint (TEST-001)."""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AnalysisFramework, Message, Scenario, Session, User


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create test user."""
    user = User(username="test_user_001", nickname="테스트교사")
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for authorization tests."""
    user = User(username="other_user_001", nickname="다른교사")
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
    """Create test analysis framework."""
    framework = AnalysisFramework(
        name="Test Framework",
        description="For testing",
        labels_json=json.dumps(["Label1", "Label2", "Label3"]),
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


@pytest.fixture
async def test_student_template(db_session: AsyncSession):
    """Create test student template."""
    from src.models.prompt_template import PromptTemplate

    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text="You are a test student bot.",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_scenario(
    db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template,
) -> Scenario:
    """Create test scenario."""
    scenario = Scenario(
        title="Test Scenario",
        prompt="Test system prompt for scenario",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


class TestGetMessageUpdatesWithNewMessages:
    """Test getting updates when new messages exist."""

    async def test_get_updates_with_new_messages(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        test_scenario: Scenario,
    ):
        """새 메시지가 있을 때 200 OK 및 HTML 반환 확인."""
        # Create session
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Add messages
        message1 = Message(
            session_id=session.id,
            role="teacher",
            content="What is photosynthesis?",
            created_at=datetime.now(timezone.utc),
        )
        message2 = Message(
            session_id=session.id,
            role="student",
            content="I think it's about plants.",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add_all([message1, message2])
        await db_session.commit()

        # Login and get updates
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Get message updates
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates", cookies=cookies
        )

        # Assertions
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Check that messages are in HTML
        html_content = response.text
        assert (
            "message-teacher" in html_content
            or "message-student" in html_content
        )
        assert "photosynthesis" in html_content
        assert "plants" in html_content

    async def test_get_updates_returns_multiple_messages(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        test_scenario: Scenario,
    ):
        """여러 새 메시지가 모두 반환되는지 확인."""
        # Create session
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Add multiple messages
        messages = [
            Message(
                session_id=session.id,
                role="teacher",
                content=f"Message {i}",
                created_at=datetime.now(timezone.utc),
            )
            for i in range(1, 4)
        ]
        db_session.add_all(messages)
        await db_session.commit()

        # Login and get updates
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Get message updates
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates", cookies=cookies
        )

        # Assertions
        assert response.status_code == 200
        html_content = response.text

        # All messages should be present
        for i in range(1, 4):
            assert f"Message {i}" in html_content


class TestGetMessageUpdatesNoNewMessages:
    """Test getting updates when no new messages exist."""

    async def test_get_updates_no_new_messages(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        test_scenario: Scenario,
    ):
        """새 메시지가 없을 때 204 No Content 반환 확인."""
        # Create session without messages
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Get message updates
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates", cookies=cookies
        )

        # Assertions
        assert response.status_code == 204
        assert response.text == ""


class TestGetMessageUpdatesWithSinceParameter:
    """Test incremental updates using 'since' parameter."""

    async def test_get_updates_with_since_parameter(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        test_scenario: Scenario,
    ):
        """since 파라미터로 증분 조회 확인."""
        # Create session
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Add messages with specific IDs
        message1 = Message(
            session_id=session.id,
            role="teacher",
            content="First message",
            created_at=datetime.now(timezone.utc),
        )
        message2 = Message(
            session_id=session.id,
            role="teacher",
            content="Second message",
            created_at=datetime.now(timezone.utc),
        )
        message3 = Message(
            session_id=session.id,
            role="teacher",
            content="Third message",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add_all([message1, message2, message3])
        await db_session.commit()
        await db_session.refresh(message1)
        await db_session.refresh(message2)
        await db_session.refresh(message3)

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Get updates since message2
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates?since={message2.id}",
            cookies=cookies,
        )

        # Assertions
        assert response.status_code == 200
        html_content = response.text

        # Only message3 should be present
        assert "Third message" in html_content

        # message1 and message2 should NOT be present
        assert "First message" not in html_content
        assert "Second message" not in html_content

    async def test_get_updates_since_all_messages(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        test_scenario: Scenario,
    ):
        """since가 최신 메시지 ID일 때 204 반환 확인."""
        # Create session
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Add message
        message = Message(
            session_id=session.id,
            role="teacher",
            content="Last message",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Get updates since the last message
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates?since={message.id}",
            cookies=cookies,
        )

        # Assertions - should be 204 since no messages after it
        assert response.status_code == 204


class TestGetMessageUpdatesUnauthorized:
    """Test unauthorized access to message updates.

    These tests verify auth behavior — the session row need not exist
    because the auth check runs before any session lookup.
    """

    async def test_get_updates_htmx_unauthorized_returns_401_with_trigger(
        self,
        test_client: TestClient,
    ):
        """HTMX 요청 인증 실패 시 401 + auth-expired 트리거 반환 확인."""
        response = test_client.get(
            "/sessions/99999/messages/updates",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )

        assert response.status_code == 401
        trigger = response.headers.get("HX-Trigger", "")
        assert "auth-expired" in trigger

        data = response.json()
        assert data["code"] == "AUTH_EXPIRED"
        assert data["redirect_url"] == "/login"

    async def test_get_updates_non_htmx_unauthorized_returns_303(
        self,
        test_client: TestClient,
    ):
        """일반 요청 인증 실패 시 기존 303 리다이렉트 유지 확인."""
        response = test_client.get(
            "/sessions/99999/messages/updates",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers.get("location") == "/login"

    async def test_get_updates_unauthorized(
        self,
        test_client: TestClient,
    ):
        """인증되지 않은 요청 시 로그인 페이지로 리디렉션 확인."""
        response = test_client.get(
            "/sessions/99999/messages/updates", follow_redirects=True
        )

        # Assertions - after redirect, should show login page
        assert response.status_code == 200
        assert "login" in response.text.lower() or "username" in response.text

    async def test_get_updates_missing_session_cookie(
        self,
        test_client: TestClient,
    ):
        """세션 쿠키 없이 요청 시 로그인 페이지로 리디렉션 확인."""
        response = test_client.get(
            "/sessions/99999/messages/updates",
            cookies={"invalid": "cookie"},
            follow_redirects=True,
        )

        # Assertions - after redirect, should show login page
        assert response.status_code == 200
        assert "login" in response.text.lower() or "username" in response.text


class TestGetMessageUpdatesWrongUser:
    """Test access control for different users."""

    async def test_get_updates_wrong_user(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
        test_scenario: Scenario,
    ):
        """다른 사용자의 세션 접근 시 404 확인."""
        # Create session for test_user
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Add a message
        message = Message(
            session_id=session.id,
            role="teacher",
            content="Private message",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(message)
        await db_session.commit()

        # Login as other_user
        login_response = test_client.post(
            "/login",
            data={
                "username": other_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Try to access test_user's session
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates", cookies=cookies
        )

        # Assertions - 403 via load_session ownership check
        assert response.status_code == 403

    async def test_get_updates_nonexistent_session(
        self,
        test_client: TestClient,
        test_user: User,
    ):
        """존재하지 않는 세션 접근 시 404 확인."""
        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Try to access nonexistent session
        response = test_client.get(
            "/sessions/99999/messages/updates", cookies=cookies
        )

        # Assertions
        assert response.status_code == 404


class TestGetMessageUpdatesEdgeCases:
    """Test edge cases and limits."""

    async def test_get_updates_respects_limit(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        test_scenario: Scenario,
    ):
        """50개 제한이 적용되는지 확인 (엔드포인트의 limit=50)."""
        # Create session
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Add 60 messages (more than limit)
        messages = [
            Message(
                session_id=session.id,
                role="teacher",
                content=f"Message {i}",
                created_at=datetime.now(timezone.utc),
            )
            for i in range(60)
        ]
        db_session.add_all(messages)
        await db_session.commit()

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Get updates
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates", cookies=cookies
        )

        # Assertions
        assert response.status_code == 200
        html_content = response.text

        # Count message divs (rough check - should be <= 50)
        message_count = html_content.count('class="message message-')
        assert message_count <= 50

    async def test_get_updates_with_different_roles(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_user: User,
        test_scenario: Scenario,
    ):
        """다양한 role의 메시지가 올바르게 렌더링되는지 확인."""
        # Create session
        session = Session(scenario_id=test_scenario.id, teacher_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Add messages with different roles
        messages = [
            Message(
                session_id=session.id,
                role="teacher",
                content="Teacher message",
                created_at=datetime.now(timezone.utc),
            ),
            Message(
                session_id=session.id,
                role="student",
                content="Student message",
                created_at=datetime.now(timezone.utc),
            ),
            Message(
                session_id=session.id,
                role="tutor",
                content="Tutor message",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        db_session.add_all(messages)
        await db_session.commit()

        # Login
        login_response = test_client.post(
            "/login",
            data={
                "username": test_user.username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Get updates
        response = test_client.get(
            f"/sessions/{session.id}/messages/updates", cookies=cookies
        )

        # Assertions
        assert response.status_code == 200
        html_content = response.text

        # Check all roles are present with correct CSS classes
        assert "message-teacher" in html_content
        assert "message-student" in html_content
        assert "message-tutor" in html_content

        # Check content is present
        assert "Teacher message" in html_content
        assert "Student message" in html_content
        assert "Tutor message" in html_content
