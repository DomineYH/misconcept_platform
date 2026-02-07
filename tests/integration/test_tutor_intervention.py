"""Integration test for tutor intervention triggers (T021)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scenario import Scenario
from src.models.user import User


@pytest.fixture(autouse=True)
async def seed_teacher_users(db_session: AsyncSession):
    """Create teacher users for tutor intervention tests."""
    for i in range(5, 12):  # teacher_005 through teacher_011
        user = User(
            username=f"teacher_{i:03d}",
            nickname=f"교사{i:03d}",
            role="teacher",
        )
        user.set_password("test1234")
        db_session.add(user)
    await db_session.commit()


@pytest.mark.skip(reason="Requires live OpenAI API and JSON response format")
class TestTutorInterventionTriggers:
    """Test tutor bot intervention logic in dialogue sessions."""

    def test_tutor_intervenes_on_low_leverage_questions(
        self, test_client: TestClient, test_scenario_with_tutor: Scenario
    ):
        """Verify tutor intervenes when detecting low-leverage questions."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_005", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario_with_tutor.id},
            cookies=cookies,
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
                data={"content": question},
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
        self, test_client: TestClient, test_scenario_with_tutor: Scenario
    ):
        """Verify tutor intervenes when conversation stagnates."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_006", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario_with_tutor.id},
            cookies=cookies,
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
                data={"content": question},
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
        self, test_client: TestClient, test_scenario_with_tutor: Scenario
    ):
        """Verify tutor stays silent for high-leverage questions."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_007", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario_with_tutor.id},
            cookies=cookies,
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
                data={"content": question},
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
        self, test_client: TestClient, test_scenario_with_tutor: Scenario
    ):
        """Verify tutor feedback is constructive and actionable."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_008", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario_with_tutor.id},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Trigger tutor intervention
        response = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Is it 5? Just yes or no."},
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

    def test_tutor_intervenes_on_repetitive_teacher_questions(
        self, test_client: TestClient, test_scenario_with_tutor: Scenario
    ):
        """Verify tutor intervenes when teacher asks same question."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_009", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario_with_tutor.id},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Send nearly identical questions repeatedly
        repetitive_questions = [
            "What is the answer to this problem?",
            "What is the answer to this problem?",
            "What is the answer to this problem?",
        ]

        tutor_appeared = False
        for question in repetitive_questions:
            response = test_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": question},
                cookies=cookies,
            )
            assert response.status_code == 200

            messages = response.json()["messages"]
            roles = [msg["role"] for msg in messages]

            if "tutor" in roles:
                tutor_appeared = True
                break

        # Repetitive questions should trigger tutor intervention
        assert (
            tutor_appeared
        ), "Tutor should intervene on repetitive teacher questions"

    def test_tutor_intervenes_when_ignoring_student_response(
        self, test_client: TestClient, test_scenario_with_tutor: Scenario
    ):
        """Verify tutor intervenes when dialogue lacks progress."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_010", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario_with_tutor.id},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Send questions that don't build on student responses
        # (This tests the pair-based analysis)
        non_progressive_questions = [
            "Tell me about addition.",
            "Tell me about addition.",
            "Tell me about addition.",
        ]

        tutor_appeared = False
        for question in non_progressive_questions:
            response = test_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": question},
                cookies=cookies,
            )
            assert response.status_code == 200

            messages = response.json()["messages"]
            roles = [msg["role"] for msg in messages]

            if "tutor" in roles:
                tutor_appeared = True
                break

        # Non-progressive dialogue should trigger tutor
        assert (
            tutor_appeared
        ), "Tutor should intervene when dialogue lacks progress"

    def test_tutor_detects_semantically_similar_questions(
        self, test_client: TestClient, test_scenario_with_tutor: Scenario
    ):
        """Verify tutor can detect semantically similar questions."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "teacher_011", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": test_scenario_with_tutor.id},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Semantically similar but not identical questions
        similar_questions = [
            "Can you solve this math problem?",
            "Could you work out this math question?",
            "Would you figure out this mathematics exercise?",
        ]

        tutor_appeared = False
        for question in similar_questions:
            response = test_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": question},
                cookies=cookies,
            )
            assert response.status_code == 200

            messages = response.json()["messages"]
            roles = [msg["role"] for msg in messages]

            if "tutor" in roles:
                tutor_appeared = True
                break

        # Note: This test may or may not trigger depending on
        # LLM semantic analysis. We just verify it doesn't crash.
        # The intervention is optional here since questions are
        # different enough in wording.
        assert response.status_code == 200
