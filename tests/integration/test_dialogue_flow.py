"""Integration test for full dialogue flow (T020)."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scenario import Scenario
from src.models.user import User
from src.models.user_group import UserGroup


@pytest.fixture(autouse=True)
async def seed_extra_teachers(
    db_session: AsyncSession,
    test_group: UserGroup,
):
    """Create additional teachers for multi-user tests."""
    for i in range(2, 5):
        user = User(
            username=f"teacher_{i:03d}",
            nickname=f"교사{i:03d}",
            role="teacher",
            group_id=test_group.id,
        )
        user.set_password("test1234")
        db_session.add(user)
    await db_session.commit()


class TestFullDialogueFlow:
    """Test complete teacher dialogue session workflow."""

    @patch("src.api.routes.session_messages.SessionManager")
    @patch("src.api.routes.session_analysis.analyze_session")
    async def test_complete_dialogue_session_flow(
        self,
        mock_analyze,
        mock_session_manager,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
        teacher_user: User,
    ):
        """Test full flow: login -> select scenario -> dialogue."""
        # Setup mocks
        mock_analyze.return_value = {
            "distribution": {"high_leverage": 2},
            "feedback": "Good questioning technique.",
        }

        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = 1
        mock_msg.role = "teacher"
        mock_msg.content = "What is 2 + 2?"
        mock_msg.created_at = datetime(2025, 1, 1)

        student_msg = AsyncMock()
        student_msg.id = 2
        student_msg.session_id = 1
        student_msg.role = "student"
        student_msg.content = "I think it's 4."
        student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

        mock_instance = AsyncMock()
        mock_instance.process_teacher_message.return_value = [
            mock_msg,
            student_msg,
        ]
        mock_session_manager.return_value = mock_instance

        # Step 1: Teacher login
        login_response = test_client.post(
            "/login",
            data={
                "username": teacher_user.username,
                "password": "test1234",
            },
        )
        assert login_response.status_code in [200, 303]
        cookies = login_response.cookies

        # Step 2: View scenario list
        scenarios_response = test_client.get("/scenarios", cookies=cookies)
        assert scenarios_response.status_code == 200
        assert "text/html" in scenarios_response.headers["content-type"]

        # Step 3: Create dialogue session
        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario.id},
            cookies=cookies,
        )
        assert session_response.status_code == 201
        session_data = session_response.json()
        session_id = session_data["id"]
        assert session_data["scenario_id"] == test_scenario.id

        # Step 4: First teacher question
        msg1_response = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "What is 2 + 2?"},
            cookies=cookies,
        )
        assert msg1_response.status_code == 200
        assert "text/html" in msg1_response.headers["content-type"]
        assert 'class="message' in msg1_response.text

        # Step 5: Second teacher question (follow-up)
        mock_msg2 = AsyncMock()
        mock_msg2.id = 3
        mock_msg2.session_id = session_id
        mock_msg2.role = "teacher"
        mock_msg2.content = "Can you explain your reasoning?"
        mock_msg2.created_at = datetime(2025, 1, 1, 0, 1)

        student_msg2 = AsyncMock()
        student_msg2.id = 4
        student_msg2.session_id = session_id
        student_msg2.role = "student"
        student_msg2.content = "Because 2+2 equals 4."
        student_msg2.created_at = datetime(2025, 1, 1, 0, 1, 1)

        mock_instance.process_teacher_message.return_value = [
            mock_msg2,
            student_msg2,
        ]

        msg2_response = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Can you explain your reasoning?"},
            cookies=cookies,
        )
        assert msg2_response.status_code == 200
        assert "text/html" in msg2_response.headers["content-type"]

        # Step 6: End session
        end_response = test_client.post(
            f"/sessions/{session_id}/end", cookies=cookies
        )
        assert end_response.status_code == 200
        end_data = end_response.json()
        assert end_data["ended"] is True
        assert "ended_at" in end_data

        # Step 7: Analyze session
        analyze_response = test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        assert analyze_response.status_code == 200
        summary = analyze_response.json()

        assert "distribution" in summary
        assert "feedback" in summary
        assert isinstance(summary["distribution"], dict)

        # Step 8: Export session to CSV
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv",
            cookies=cookies,
        )
        assert export_response.status_code == 200
        assert "text/csv" in export_response.headers["content-type"]

    @patch("src.api.routes.session_messages.SessionManager")
    async def test_dialogue_maintains_conversation_context(
        self,
        mock_session_manager,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """Verify chatbots maintain context across messages."""
        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = 1
        mock_msg.role = "teacher"
        mock_msg.content = "My name is Teacher Lee. What's yours?"
        mock_msg.created_at = datetime(2025, 1, 1)

        student_msg = AsyncMock()
        student_msg.id = 2
        student_msg.session_id = 1
        student_msg.role = "student"
        student_msg.content = "Hello Teacher Lee!"
        student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

        mock_instance = AsyncMock()
        mock_instance.process_teacher_message.return_value = [
            mock_msg,
            student_msg,
        ]
        mock_session_manager.return_value = mock_instance

        # Login as teacher_002
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_002",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario.id},
            cookies=cookies,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        # First question establishes context
        msg1 = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": ("My name is Teacher Lee." " What's yours?")},
            cookies=cookies,
        )
        assert msg1.status_code == 200
        assert "text/html" in msg1.headers["content-type"]
        assert 'class="message' in msg1.text

        # Second question references previous context
        mock_msg2 = AsyncMock()
        mock_msg2.id = 3
        mock_msg2.session_id = session_id
        mock_msg2.role = "teacher"
        mock_msg2.content = "Can you remember my name?"
        mock_msg2.created_at = datetime(2025, 1, 1, 0, 1)

        student_msg2 = AsyncMock()
        student_msg2.id = 4
        student_msg2.session_id = session_id
        student_msg2.role = "student"
        student_msg2.content = "Yes, Teacher Lee!"
        student_msg2.created_at = datetime(2025, 1, 1, 0, 1, 1)

        mock_instance.process_teacher_message.return_value = [
            mock_msg2,
            student_msg2,
        ]

        msg2 = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Can you remember my name?"},
            cookies=cookies,
        )
        assert msg2.status_code == 200
        assert "text/html" in msg2.headers["content-type"]
        assert 'class="message' in msg2.text

    @patch("src.api.routes.session_messages.SessionManager")
    async def test_multiple_concurrent_sessions(
        self,
        mock_session_manager,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """Verify system handles multiple teacher sessions."""
        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = 1
        mock_msg.role = "teacher"
        mock_msg.content = "Teacher question"
        mock_msg.created_at = datetime(2025, 1, 1)

        student_msg = AsyncMock()
        student_msg.id = 2
        student_msg.session_id = 1
        student_msg.role = "student"
        student_msg.content = "Student response"
        student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

        mock_instance = AsyncMock()
        mock_instance.process_teacher_message.return_value = [
            mock_msg,
            student_msg,
        ]
        mock_session_manager.return_value = mock_instance

        # Login two different teachers
        teacher3_cookies = test_client.post(
            "/login",
            data={
                "username": "teacher_003",
                "password": "test1234",
            },
        ).cookies

        teacher4_cookies = test_client.post(
            "/login",
            data={
                "username": "teacher_004",
                "password": "test1234",
            },
        ).cookies

        # Both create sessions
        session1_resp = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario.id},
            cookies=teacher3_cookies,
        )
        assert session1_resp.status_code == 201
        session1 = session1_resp.json()["id"]

        session2_resp = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario.id},
            cookies=teacher4_cookies,
        )
        assert session2_resp.status_code == 201
        session2 = session2_resp.json()["id"]

        assert session1 != session2

        # Both send messages independently
        msg1 = test_client.post(
            f"/sessions/{session1}/messages",
            data={"content": "Teacher 3 question"},
            cookies=teacher3_cookies,
        )

        msg2 = test_client.post(
            f"/sessions/{session2}/messages",
            data={"content": "Teacher 4 question"},
            cookies=teacher4_cookies,
        )

        assert msg1.status_code == 200
        assert "text/html" in msg1.headers["content-type"]
        assert 'class="message' in msg1.text

        assert msg2.status_code == 200
        assert "text/html" in msg2.headers["content-type"]
        assert 'class="message' in msg2.text
