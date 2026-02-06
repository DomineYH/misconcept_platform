"""Integration test for full dialogue flow (T020)."""
import pytest
from fastapi.testclient import TestClient


class TestFullDialogueFlow:
    """Test complete teacher dialogue session workflow."""

    def test_complete_dialogue_session_flow(
        self, test_client: TestClient
    ):
        """Test full flow: login → select scenario → multi-turn dialogue."""
        # Step 1: Teacher login
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_001", "password": "test1234"},
        )
        assert login_response.status_code == 303
        cookies = login_response.cookies

        # Step 2: View scenario list
        scenarios_response = test_client.get(
            "/scenarios", cookies=cookies
        )
        assert scenarios_response.status_code == 200
        assert "text/html" in scenarios_response.headers["content-type"]

        # Step 3: Create dialogue session
        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        assert session_response.status_code == 201
        session_data = session_response.json()
        session_id = session_data["id"]
        assert session_data["scenario_id"] == 1

        # Step 4: First teacher question
        msg1_response = test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "What is 2 + 2?"},
            cookies=cookies,
        )
        assert msg1_response.status_code == 200
        msg1_data = msg1_response.json()
        messages_1 = msg1_data["messages"]

        # Should have at least teacher message + student response
        assert len(messages_1) >= 2

        # Verify message roles
        roles = [msg["role"] for msg in messages_1]
        assert "teacher" in roles
        assert "student" in roles

        # Step 5: Second teacher question (follow-up)
        msg2_response = test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Can you explain your reasoning?"},
            cookies=cookies,
        )
        assert msg2_response.status_code == 200
        msg2_data = msg2_response.json()
        messages_2 = msg2_data["messages"]

        # Should include new messages
        assert len(messages_2) >= 1

        # Step 6: Third question that might trigger tutor
        msg3_response = test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "What do you think about that?"},
            cookies=cookies,
        )
        assert msg3_response.status_code == 200

        # Step 7: End session
        end_response = test_client.post(
            f"/sessions/{session_id}/end", cookies=cookies
        )
        assert end_response.status_code == 200
        end_data = end_response.json()
        assert end_data["ended"] is True
        assert "ended_at" in end_data

        # Step 7b: Analyze session
        analyze_response = test_client.post(
            f"/sessions/{session_id}/analyze", cookies=cookies
        )
        assert analyze_response.status_code == 200
        summary = analyze_response.json()

        # Verify summary structure
        assert "distribution" in summary
        assert "feedback" in summary
        assert isinstance(summary["distribution"], dict)

        # Step 8: Export session to CSV
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )
        assert export_response.status_code == 200
        assert "text/csv" in export_response.headers["content-type"]

    def test_dialogue_maintains_conversation_context(
        self, test_client: TestClient
    ):
        """Verify chatbots maintain context across messages."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_002", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # First question establishes context
        msg1 = test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "My name is Teacher Lee. What's yours?"},
            cookies=cookies,
        )
        assert msg1.status_code == 200

        # Second question references previous context
        msg2 = test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Can you remember my name?"},
            cookies=cookies,
        )
        assert msg2.status_code == 200
        messages = msg2.json()["messages"]

        # Student bot should reference context
        # (exact validation depends on bot implementation)
        assert len(messages) >= 1

    def test_multiple_concurrent_sessions(
        self, test_client: TestClient
    ):
        """Verify system handles multiple teacher sessions."""
        # Create two different teacher sessions
        teacher1_cookies = test_client.post(
            "/login",
            data={"username": "teacher_003", "password": "test1234"},
        ).cookies

        teacher2_cookies = test_client.post(
            "/login",
            data={"username": "teacher_004", "password": "test1234"},
        ).cookies

        # Both create sessions
        session1 = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=teacher1_cookies
        ).json()["id"]

        session2 = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=teacher2_cookies
        ).json()["id"]

        assert session1 != session2

        # Both send messages independently
        msg1 = test_client.post(
            f"/sessions/{session1}/messages",
            json={"content": "Teacher 1 question"},
            cookies=teacher1_cookies,
        )

        msg2 = test_client.post(
            f"/sessions/{session2}/messages",
            json={"content": "Teacher 2 question"},
            cookies=teacher2_cookies,
        )

        assert msg1.status_code == 200
        assert msg2.status_code == 200
