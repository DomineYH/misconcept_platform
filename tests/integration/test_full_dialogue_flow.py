"""
Integration test for full dialogue flow: User-Chatbot-Tutor.

Tests the complete conversation flow:
1. Session creation with scenario
2. User sends message -> Chatbot responds
3. Tutor analyzes conversation and provides feedback
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.user import User


@pytest.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create test admin user (bypasses group check)."""
    user = User(
        username="test_teacher_001",
        nickname="Test Teacher",
        role="admin",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def test_scenario(
    async_session: AsyncSession,
    test_user: User,
) -> Scenario:
    """Create test scenario with framework and templates.

    Creates templates inline to avoid cross-engine FK violations
    (integration conftest's test_student_template uses db_session,
    a separate in-memory engine from async_session).
    """
    # Create student template in same session
    student_tpl = PromptTemplate(
        bot_type="student",
        template_name="Dialogue Flow Student Template",
        version=1,
        template_text=(
            "You are a test student bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    async_session.add(student_tpl)
    await async_session.flush()

    # Create tutor template in same session
    tutor_tpl = PromptTemplate(
        bot_type="tutor",
        template_name="Dialogue Flow Tutor Template",
        version=1,
        template_text=(
            "You are a test tutor bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    async_session.add(tutor_tpl)
    await async_session.flush()

    framework = AnalysisFramework(
        name="High/Low Leverage",
        description="Test framework for dialogue analysis",
        labels_json='["High Leverage", "Low Leverage"]',
    )
    async_session.add(framework)
    await async_session.flush()

    scenario = Scenario(
        title="Fraction Addition Misconception",
        prompt=(
            "You are a student who believes that when adding "
            "fractions, you add both numerators and denominators. "
            "For example, 1/2 + 1/3 = 2/5. Maintain this "
            "misconception consistently."
        ),
        student_profile="Middle school student learning fractions",
        is_active=1,
        framework_id=framework.id,
        student_template_id=student_tpl.id,
        tutor_template_id=tutor_tpl.id,
        created_by=test_user.id,
    )
    async_session.add(scenario)
    await async_session.flush()
    return scenario


@pytest.mark.asyncio
@patch("src.api.routes.session_messages.SessionManager")
@patch("src.api.routes.session_analysis.analyze_session")
async def test_full_dialogue_flow(
    mock_analyze,
    mock_session_manager,
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_scenario: Scenario,
    test_user: User,
):
    """
    Test complete dialogue flow with user, chatbot, and tutor.

    Flow:
    1. Create session with scenario
    2. User asks question
    3. Chatbot responds with misconception
    4. Session ended then analyzed
    """
    # Setup analyze mock
    mock_analyze.return_value = {
        "distribution": {"High Leverage": 1, "Low Leverage": 0},
        "feedback": "Good questioning technique.",
    }

    # Setup SessionManager mock
    mock_msg = AsyncMock()
    mock_msg.id = 1
    mock_msg.session_id = 1
    mock_msg.role = "teacher"
    mock_msg.content = "How do I add 1/2 and 1/3?"
    mock_msg.created_at = datetime(2025, 1, 1)

    student_msg = AsyncMock()
    student_msg.id = 2
    student_msg.session_id = 1
    student_msg.role = "student"
    student_msg.content = "Just add tops and bottoms: 2/5!"
    student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

    mock_instance = AsyncMock()
    mock_instance.process_teacher_message.return_value = [
        mock_msg,
        student_msg,
    ]
    mock_session_manager.return_value = mock_instance

    # Step 0: Login
    login_response = await async_client.post(
        "/login",
        data={
            "username": test_user.username,
            "password": "test1234",
        },
    )
    assert login_response.status_code in [200, 303]

    # Step 1: Verify test scenario
    assert test_scenario is not None
    assert test_scenario.tutor_enabled is True

    # Step 2: Create new session
    session_response = await async_client.post(
        "/sessions",
        json={"scenario_id": test_scenario.id},
    )
    assert session_response.status_code in [200, 201]
    session_data = session_response.json()
    session_id = session_data["id"]

    assert "scenario_id" in session_data
    assert session_data["scenario_id"] == test_scenario.id

    # Step 3: User sends first message
    user_message = "How do I add 1/2 and 1/3?"
    msg_response = await async_client.post(
        f"/sessions/{session_id}/messages",
        data={"content": user_message},
    )
    assert msg_response.status_code == 200
    assert "text/html" in msg_response.headers.get("content-type", "")
    html_response = msg_response.text
    assert len(html_response) > 0
    assert 'class="message' in html_response

    # Step 4: End session before analysis
    end_response = await async_client.post(f"/sessions/{session_id}/end")
    assert end_response.status_code == 200
    assert end_response.json()["ended"] is True

    # Step 5: Analyze the conversation
    analysis_response = await async_client.post(
        f"/sessions/{session_id}/analyze"
    )
    assert analysis_response.status_code == 200
    analysis_data = analysis_response.json()

    assert "distribution" in analysis_data
    assert "feedback" in analysis_data

    # Step 6: Second conversation - need new session
    session2_response = await async_client.post(
        "/sessions",
        json={"scenario_id": test_scenario.id},
    )
    assert session2_response.status_code in [200, 201]
    session2_id = session2_response.json()["id"]

    followup_message = "So I just add the tops and bottoms?"

    followup_msg = AsyncMock()
    followup_msg.id = 3
    followup_msg.session_id = session2_id
    followup_msg.role = "teacher"
    followup_msg.content = followup_message
    followup_msg.created_at = datetime(2025, 1, 1, 0, 1)

    followup_student = AsyncMock()
    followup_student.id = 4
    followup_student.session_id = session2_id
    followup_student.role = "student"
    followup_student.content = "Yes, that's right!"
    followup_student.created_at = datetime(2025, 1, 1, 0, 1, 1)

    mock_instance.process_teacher_message.return_value = [
        followup_msg,
        followup_student,
    ]

    followup_response = await async_client.post(
        f"/sessions/{session2_id}/messages",
        data={"content": followup_message},
    )
    assert followup_response.status_code == 200
    assert "text/html" in followup_response.headers.get("content-type", "")


@pytest.mark.asyncio
@patch("src.api.routes.session_messages.SessionManager")
async def test_dialogue_flow_with_tutor_disabled(
    mock_session_manager,
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_scenario: Scenario,
    test_user: User,
):
    """Test conversation when tutor is disabled for scenario."""
    mock_msg = AsyncMock()
    mock_msg.id = 1
    mock_msg.session_id = 1
    mock_msg.role = "teacher"
    mock_msg.content = "Test question"
    mock_msg.created_at = datetime(2025, 1, 1)

    student_msg = AsyncMock()
    student_msg.id = 2
    student_msg.session_id = 1
    student_msg.role = "student"
    student_msg.content = "Test response"
    student_msg.created_at = datetime(2025, 1, 1, 0, 0, 1)

    mock_instance = AsyncMock()
    mock_instance.process_teacher_message.return_value = [
        mock_msg,
        student_msg,
    ]
    mock_session_manager.return_value = mock_instance

    # Login
    login_response = await async_client.post(
        "/login",
        data={
            "username": test_user.username,
            "password": "test1234",
        },
    )
    assert login_response.status_code in [200, 303]

    # Temporarily disable tutor by clearing template
    original_tutor_template_id = test_scenario.tutor_template_id
    test_scenario.tutor_template_id = None
    await async_session.flush()

    try:
        # Create session
        session_response = await async_client.post(
            "/sessions",
            json={"scenario_id": test_scenario.id},
        )
        assert session_response.status_code in [200, 201]
        session_id = session_response.json()["id"]

        # Send message
        msg_response = await async_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Test question"},
        )
        assert msg_response.status_code == 200
        assert "text/html" in msg_response.headers.get("content-type", "")

        # End session before analyze
        end_response = await async_client.post(f"/sessions/{session_id}/end")
        assert end_response.status_code == 200

        # Try to get analysis - should handle gracefully
        analysis_response = await async_client.post(
            f"/sessions/{session_id}/analyze"
        )
        assert analysis_response.status_code in [200, 400]

    finally:
        # Restore tutor state
        test_scenario.tutor_template_id = original_tutor_template_id
        await async_session.flush()


@pytest.mark.asyncio
@patch("src.api.routes.session_messages.SessionManager")
@patch("src.api.routes.session_analysis.analyze_session")
async def test_multiple_conversation_turns(
    mock_analyze,
    mock_session_manager,
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_scenario: Scenario,
    test_user: User,
):
    """Test multiple turns of conversation."""
    mock_analyze.return_value = {
        "distribution": {"High Leverage": 3, "Low Leverage": 2},
        "feedback": "Solid technique across 5 turns.",
    }

    def make_mock_pair(idx, session_id, user_content):
        teacher = AsyncMock()
        teacher.id = idx * 2 - 1
        teacher.session_id = session_id
        teacher.role = "teacher"
        teacher.content = user_content
        teacher.created_at = datetime(2025, 1, 1, 0, idx - 1)

        student = AsyncMock()
        student.id = idx * 2
        student.session_id = session_id
        student.role = "student"
        student.content = f"Student response {idx}"
        student.created_at = datetime(2025, 1, 1, 0, idx - 1, 1)

        return [teacher, student]

    mock_instance = AsyncMock()
    mock_session_manager.return_value = mock_instance

    # Login
    login_response = await async_client.post(
        "/login",
        data={
            "username": test_user.username,
            "password": "test1234",
        },
    )
    assert login_response.status_code in [200, 303]

    # Create session
    session_response = await async_client.post(
        "/sessions",
        json={"scenario_id": test_scenario.id},
    )
    assert session_response.status_code in [200, 201]
    session_id = session_response.json()["id"]

    conversation = [
        "How do I add fractions?",
        "What about 1/4 + 1/2?",
        "So the denominator stays 4?",
        "But why can't I add the bottoms?",
        "Can you show me an example?",
    ]

    for i, user_msg in enumerate(conversation, 1):
        mock_instance.process_teacher_message.return_value = make_mock_pair(
            i, session_id, user_msg
        )

        response = await async_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": user_msg},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert 'class="message' in response.text

    # End session before analysis
    end_response = await async_client.post(f"/sessions/{session_id}/end")
    assert end_response.status_code == 200

    # Get final analysis
    analysis_response = await async_client.post(
        f"/sessions/{session_id}/analyze"
    )
    assert analysis_response.status_code == 200
    analysis_data = analysis_response.json()
    assert "distribution" in analysis_data
    assert "feedback" in analysis_data
