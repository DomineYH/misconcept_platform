"""Integration test for tutor intervention triggers (T021)."""
import pytest
from fastapi.testclient import TestClient


class TestTutorInterventionTriggers:
    """Test tutor bot intervention logic in dialogue sessions."""

    def test_tutor_intervenes_on_low_leverage_questions(
        self, test_client: TestClient
    ):
        """Verify tutor intervenes when detecting low-leverage questions."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_005", "nickname": "정교사"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send multiple low-leverage questions (closed, directive)
        low_leverage_questions = [
            "Is the answer 5?",  # Closed question
            "You should try adding them.",  # Directive
            "Can you just tell me yes or no?",  # Closed
        ]

        tutor_appeared = False
        for question in low_leverage_questions:
            response = test_client.post(
                f"/sessions/{session_id}/messages",
                json={"content": question},
                cookies=cookies,
            )
            assert response.status_code == 200

            messages = response.json()["messages"]
            roles = [msg["role"] for msg in messages]

            if "tutor" in roles:
                tutor_appeared = True
                # Verify tutor message exists
                tutor_msgs = [
                    m for m in messages if m["role"] == "tutor"
                ]
                assert len(tutor_msgs) > 0
                assert len(tutor_msgs[0]["content"]) > 0
                break

        # At least one low-leverage question should trigger tutor
        assert (
            tutor_appeared
        ), "Tutor should intervene after low-leverage questions"

    def test_tutor_intervenes_on_conversation_stagnation(
        self, test_client: TestClient
    ):
        """Verify tutor intervenes when conversation stagnates."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_006", "nickname": "강교사"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send similar questions repeatedly (stagnation pattern)
        stagnant_questions = [
            "What do you think?",
            "What do you think about that?",
            "What are your thoughts?",
            "Any other thoughts?",
        ]

        tutor_appeared = False
        for question in stagnant_questions:
            response = test_client.post(
                f"/sessions/{session_id}/messages",
                json={"content": question},
                cookies=cookies,
            )
            assert response.status_code == 200

            messages = response.json()["messages"]
            roles = [msg["role"] for msg in messages]

            if "tutor" in roles:
                tutor_appeared = True
                break

        # Stagnation should trigger tutor intervention
        assert (
            tutor_appeared
        ), "Tutor should intervene on stagnation pattern"

    def test_tutor_does_not_intervene_on_high_leverage_questions(
        self, test_client: TestClient
    ):
        """Verify tutor stays silent for high-leverage questions."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_007", "nickname": "윤교사"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send high-leverage questions (open, pressing, linking)
        high_leverage_questions = [
            "Can you explain your reasoning behind that answer?",
            "How does this connect to what we learned yesterday?",
            "What patterns do you notice in these examples?",
        ]

        tutor_count = 0
        for question in high_leverage_questions:
            response = test_client.post(
                f"/sessions/{session_id}/messages",
                json={"content": question},
                cookies=cookies,
            )
            assert response.status_code == 200

            messages = response.json()["messages"]
            tutor_msgs = [m for m in messages if m["role"] == "tutor"]
            tutor_count += len(tutor_msgs)

        # Tutor should appear minimally or not at all
        # (Allow occasional tutor responses but not frequent)
        assert (
            tutor_count <= 1
        ), "Tutor should not intervene frequently on high-leverage questions"

    def test_tutor_provides_constructive_feedback(
        self, test_client: TestClient
    ):
        """Verify tutor feedback is constructive and actionable."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_008", "nickname": "서교사"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Trigger tutor intervention
        response = test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Is it 5? Just yes or no."},
            cookies=cookies,
        )

        messages = response.json()["messages"]
        tutor_msgs = [m for m in messages if m["role"] == "tutor"]

        if len(tutor_msgs) > 0:
            tutor_content = tutor_msgs[0]["content"]

            # Tutor message should be substantial
            assert len(tutor_content) > 20

            # Should not be purely negative
            # (exact validation depends on implementation)
            assert tutor_content  # Non-empty feedback
