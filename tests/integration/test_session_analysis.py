"""Integration test for session analysis workflow (T053)."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scenario import Scenario
from src.models.user import User


@pytest.fixture(autouse=True)
async def seed_analysis_test_data(
    db_session: AsyncSession,
    test_scenario: Scenario,
    test_group,
):
    """Seed extra teacher users for analysis tests."""
    for i in range(1, 4):
        user = User(
            username=f"teacher_{i:03d}",
            nickname=f"교사{i:03d}",
            role="teacher",
            group_id=test_group.id,
        )
        user.set_password("test1234")
        db_session.add(user)
    await db_session.commit()


class TestSessionAnalysisWorkflow:
    """Test complete session analysis workflow (T053)."""

    @patch("src.api.routes.session_analysis.analyze_session")
    @patch("src.api.routes.session_messages.SessionManager")
    async def test_complete_dialogue_triggers_question_analysis(
        self,
        mock_session_manager,
        mock_analyze,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """
        Verify complete dialogue -> end session -> analysis.

        Workflow:
        1. Teacher logs in
        2. Creates session with scenario
        3. Sends multiple teacher messages
        4. Ends session
        5. Verify /analyze returns distribution and feedback
        """
        # Setup SessionManager mock
        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = 1
        mock_msg.role = "teacher"
        mock_msg.content = "Test"
        mock_msg.created_at = datetime(2025, 1, 1)

        student_msg = AsyncMock()
        student_msg.id = 2
        student_msg.session_id = 1
        student_msg.role = "student"
        student_msg.content = "Response"
        student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

        mock_instance = AsyncMock()
        mock_instance.process_teacher_message.return_value = [
            mock_msg,
            student_msg,
        ]
        mock_session_manager.return_value = mock_instance

        # Setup analyze mock
        mock_analyze.return_value = {
            "distribution": {
                "high_leverage": 2,
                "medium_leverage": 1,
                "low_leverage": 0,
            },
            "feedback": "Good questioning.",
        }

        # Step 1: Login
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_001",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies
        assert login_response.status_code in [
            200,
            302,
            303,
        ]

        # Step 2: Create session
        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario.id},
            cookies=cookies,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        # Step 3: Send multiple teacher messages
        teacher_messages = [
            "What is photosynthesis?",
            "Can you explain more?",
            "Is it related to sunlight?",
        ]

        for content in teacher_messages:
            msg_response = test_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": content},
                cookies=cookies,
            )
            assert msg_response.status_code == 200

        # Step 4: End session
        end_response = test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        assert end_response.status_code == 200
        end_data = end_response.json()
        assert end_data["ended"] is True
        assert "ended_at" in end_data

        # Step 5: Analyze session
        analyze_response = test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        assert analyze_response.status_code == 200
        data = analyze_response.json()
        assert "distribution" in data
        assert "feedback" in data
        assert data["feedback"] == "Good questioning."

    @patch("src.api.routes.session_analysis.analyze_session")
    async def test_session_with_no_teacher_messages(
        self,
        mock_analyze,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """Verify empty session can be ended and analyzed."""
        mock_analyze.return_value = {
            "distribution": {
                "high_leverage": 0,
                "medium_leverage": 0,
                "low_leverage": 0,
            },
            "feedback": "No questions to analyze.",
        }

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

        # End session immediately without messages
        end_response = test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        assert end_response.status_code == 200

        # Analyze session
        analyze_response = test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        assert analyze_response.status_code == 200
        data = analyze_response.json()
        assert "distribution" in data
        assert "feedback" in data

    @patch("src.api.routes.session_analysis.analyze_session")
    @patch("src.api.routes.session_messages.SessionManager")
    async def test_question_analysis_labels_match_framework(
        self,
        mock_session_manager,
        mock_analyze,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """Verify analysis response structure."""
        mock_msg = AsyncMock()
        mock_msg.id = 1
        mock_msg.session_id = 1
        mock_msg.role = "teacher"
        mock_msg.content = "Explain your thinking."
        mock_msg.created_at = datetime(2025, 1, 1)

        student_msg = AsyncMock()
        student_msg.id = 2
        student_msg.session_id = 1
        student_msg.role = "student"
        student_msg.content = "I think..."
        student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

        mock_instance = AsyncMock()
        mock_instance.process_teacher_message.return_value = [
            mock_msg,
            student_msg,
        ]
        mock_session_manager.return_value = mock_instance

        mock_analyze.return_value = {
            "distribution": {
                "high_leverage": 1,
                "medium_leverage": 0,
                "low_leverage": 0,
            },
            "feedback": "Good technique.",
        }

        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_003",
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

        # Send message
        msg_resp = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Explain your thinking."},
            cookies=cookies,
        )
        assert msg_resp.status_code == 200

        # End and analyze
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        analyze_resp = test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        assert analyze_resp.status_code == 200
        data = analyze_resp.json()

        # Verify structure
        assert "distribution" in data
        assert "feedback" in data
        dist = data["distribution"]
        assert "high_leverage" in dist
        assert "medium_leverage" in dist
        assert "low_leverage" in dist
