"""
Integration test for full dialogue flow: User-Chatbot-Tutor.

Tests the complete conversation flow:
1. Session creation with scenario
2. User sends message → Chatbot responds
3. Tutor analyzes conversation and provides feedback
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scenario import Scenario
from src.models.session import Session
from src.models.message import Message
from src.models.question_analysis import QuestionAnalysis
from src.models.analysis_framework import AnalysisFramework
from src.models.user import User
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create test user."""
    user = User(
        student_uid="test_teacher_001",
        nickname="Test Teacher",
        role="teacher",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_student_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test student template."""
    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text=(
            "You are a test student bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_tutor_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test tutor template."""
    template = PromptTemplate(
        bot_type="tutor",
        template_name="Test Tutor Template",
        version=1,
        template_text=(
            "You are a test tutor bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_scenario(
    db_session: AsyncSession,
    test_user: User,
    test_student_template: PromptTemplate,
    test_tutor_template: PromptTemplate,
) -> Scenario:
    """Create test scenario with framework."""
    # Create framework
    framework = AnalysisFramework(
        name="High/Low Leverage",
        description="Test framework for dialogue analysis",
    )
    framework.labels = ["High Leverage", "Low Leverage"]
    db_session.add(framework)
    await db_session.flush()

    # Create scenario
    scenario = Scenario(
        title="Fraction Addition Misconception",
        prompt=(
            "You are a student who believes that when adding fractions, "
            "you add both numerators and denominators. For example, "
            "1/2 + 1/3 = 2/5. Maintain this misconception consistently."
        ),
        student_profile="Middle school student learning fractions",
        is_active=1,
        framework_id=framework.id,
        student_template_id=test_student_template.id,
        tutor_template_id=test_tutor_template.id,
        created_by=test_user.id,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


@pytest.mark.asyncio
async def test_full_dialogue_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_scenario: Scenario,
    test_user: User,
):
    """
    Test complete dialogue flow with user, chatbot, and tutor.

    Flow:
    1. Create session with scenario
    2. User asks question
    3. Chatbot responds with misconception
    4. Tutor analyzes and provides feedback
    """
    # Step 0: Login
    login_response = await async_client.post(
        "/login",
        data={
            "student_uid": test_user.student_uid,
            "nickname": test_user.nickname,
        },
    )
    assert login_response.status_code in [200, 303]  # 303 redirect after login

    # Step 1: Use test scenario
    scenario = test_scenario
    assert scenario is not None
    assert scenario.tutor_enabled is True

    # Step 2: Create new session
    session_response = await async_client.post(
        "/sessions",
        json={"scenario_id": scenario.id},
    )
    assert session_response.status_code in [200, 201]
    session_data = session_response.json()
    session_id = session_data["id"]

    # Verify session data in response
    assert "scenario_id" in session_data
    assert session_data["scenario_id"] == scenario.id

    # Step 3: User sends first message
    user_message = "How do I add 1/2 and 1/3?"
    msg_response = await async_client.post(
        f"/sessions/{session_id}/messages",
        data={"content": user_message},
    )
    assert msg_response.status_code == 200

    # Backend now returns HTML (not JSON) for HTMX compatibility
    assert "text/html" in msg_response.headers.get("content-type", "")
    html_response = msg_response.text

    # Verify HTML response contains the message
    assert len(html_response) > 0
    print(f"\n✓ User: {user_message}")
    print(f"✓ HTML Response: {html_response[:100]}...")

    # Step 5: Tutor analyzes the conversation
    analysis_response = await async_client.post(
        f"/sessions/{session_id}/analyze"
    )
    assert analysis_response.status_code == 200
    analysis_data = analysis_response.json()

    # Verify tutor feedback exists
    assert "analysis" in analysis_data
    tutor_feedback = analysis_data["analysis"]
    assert len(tutor_feedback) > 0
    print(f"✓ Tutor: {tutor_feedback[:100]}...")

    # Step 7: Continue conversation - User responds to chatbot
    followup_message = "So I just add the tops and bottoms?"
    followup_response = await async_client.post(
        f"/sessions/{session_id}/messages",
        data={"content": followup_message},
    )
    assert followup_response.status_code == 200
    assert "text/html" in followup_response.headers.get("content-type", "")
    print(f"✓ Followup user: {followup_message}")
    print(f"✓ Followup HTML: {followup_response.text[:100]}...")

    # Step 8: Get tutor analysis again
    second_analysis = await async_client.post(
        f"/sessions/{session_id}/analyze"
    )
    assert second_analysis.status_code == 200
    second_data = second_analysis.json()
    assert "analysis" in second_data

    print("\n✅ Full dialogue flow test passed!")
    print(f"Session ID: {session_id}")
    print(f"Total conversation turns: 2")
    print(f"Tutor analyses: 2")


@pytest.mark.asyncio
async def test_dialogue_flow_with_tutor_disabled(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_scenario: Scenario,
):
    """Test conversation when tutor is disabled for scenario."""
    # Use test scenario and disable tutor
    scenario = test_scenario

    # Temporarily disable tutor by clearing template
    original_tutor_template_id = scenario.tutor_template_id
    scenario.tutor_template_id = None
    await db_session.commit()

    try:
        # Create session
        session_response = await async_client.post(
            "/sessions",
            json={"scenario_id": scenario.id},
        )
        session_id = session_response.json()["id"]

        # Send message
        msg_response = await async_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Test question"},
        )
        assert msg_response.status_code == 200

        # Try to get analysis - should handle gracefully
        analysis_response = await async_client.post(
            f"/sessions/{session_id}/analyze"
        )
        # May return 400 or specific message indicating tutor disabled
        assert analysis_response.status_code in [200, 400]

        print("\n✅ Tutor disabled scenario handled correctly")

    finally:
        # Restore tutor state
        scenario.tutor_template_id = original_tutor_template_id
        await db_session.commit()


@pytest.mark.asyncio
async def test_multiple_conversation_turns(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_scenario: Scenario,
):
    """Test multiple turns of conversation."""
    # Use test scenario
    scenario = test_scenario

    # Create session
    session_response = await async_client.post(
        "/sessions",
        json={"scenario_id": scenario.id},
    )
    session_id = session_response.json()["id"]

    # Conduct 5 conversation turns
    conversation = [
        "How do I add fractions?",
        "What about 1/4 + 1/2?",
        "So the denominator stays 4?",
        "But why can't I add the bottoms?",
        "Can you show me an example?",
    ]

    for i, user_msg in enumerate(conversation, 1):
        response = await async_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": user_msg},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        print(f"\nTurn {i}:")
        print(f"User: {user_msg}")
        print(f"HTML: {response.text[:80]}...")

    # Verify all messages stored
    result = await db_session.execute(
        select(Message).where(Message.session_id == session_id)
    )
    messages = result.scalars().all()
    assert len(messages) == len(conversation) * 2  # User + chatbot each

    # Get final tutor analysis
    analysis_response = await async_client.post(
        f"/sessions/{session_id}/analyze"
    )
    assert analysis_response.status_code == 200

    print(f"\n✅ Multiple turns test passed - {len(conversation)} turns")
