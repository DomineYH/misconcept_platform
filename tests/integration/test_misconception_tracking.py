"""Integration tests for misconception tracking and analysis."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Message
from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.user import User


def _make_student_bot_mock():
    """Build a StudentBot mock that returns a string response.

    The mock exposes a string .model so the API usage log
    INSERT does not fail with an AsyncMock type error.
    """
    mock_bot = AsyncMock()
    mock_bot.model = "gpt-4-turbo"
    mock_bot.generate_response = AsyncMock(
        return_value=(
            "Student answer text",
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        )
    )
    return mock_bot


@pytest.fixture(autouse=True)
async def seed_misconception_test_data(
    async_session: AsyncSession,
):
    """Seed test data for misconception tracking tests."""
    # Use admin role so group check is bypassed
    user = User(
        username="test_teacher",
        nickname="테스트교사",
        role="admin",
    )
    user.set_password("test1234")
    async_session.add(user)

    # Create framework
    framework = AnalysisFramework(
        name="Misconception Framework",
        description="Framework for misconception tests",
        labels_json=(
            '["high_leverage",' ' "medium_leverage",' ' "low_leverage"]'
        ),
    )
    async_session.add(framework)
    await async_session.flush()

    # Create template
    template = PromptTemplate(
        bot_type="student",
        template_name="Misconception Student Template",
        version=1,
        template_text="You are a test student bot.",
    )
    async_session.add(template)
    await async_session.flush()

    # Create scenario (id=1 since first in DB)
    scenario = Scenario(
        title="Misconception Test Scenario",
        prompt="Test prompt for misconception tracking",
        student_profile="Test student profile",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    async_session.add(scenario)
    await async_session.commit()


@pytest.mark.asyncio
async def test_student_response_analyzed_for_misconception(
    async_session, async_client
):
    """Verify misconception analysis on student responses."""
    # Login
    login_response = await async_client.post(
        "/login",
        data={
            "username": "test_teacher",
            "password": "test1234",
        },
    )
    assert login_response.status_code in [200, 303]

    # Create session
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    # Mock analysis result
    mock_analysis = {
        "maintains_misconception": True,
        "misconception_strength": 0.85,
        "evidence": ("Student clearly maintains the misconception"),
        "drift_detected": False,
        "analysis_notes": "Strong adherence observed",
    }

    with (
        patch("src.services.session_mgr.StudentBot") as MockStudentBot,
        patch("src.services.session_mgr.MisconceptionAnalyzer") as MockAnalyzer,
    ):
        MockStudentBot.return_value = _make_student_bot_mock()

        mock_analyzer_instance = AsyncMock()
        mock_analyzer_instance.analyze_student_response = AsyncMock(
            return_value=mock_analysis
        )
        MockAnalyzer.return_value = mock_analyzer_instance

        # Send teacher message
        msg_response = await async_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Why do you think that?"},
        )

        assert msg_response.status_code == 200

    # Verify student message has metadata
    result = await async_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.role == "student")
        .order_by(Message.created_at)
    )
    student_messages = result.scalars().all()

    assert len(student_messages) > 0
    student_msg = student_messages[0]

    # Verify metadata exists and contains analysis
    assert student_msg.analysis_metadata is not None
    analysis = json.loads(student_msg.analysis_metadata)

    assert "maintains_misconception" in analysis
    assert "misconception_strength" in analysis
    assert analysis["maintains_misconception"] is True
    assert 0.0 <= analysis["misconception_strength"] <= 1.0
    assert "evidence" in analysis


@pytest.mark.asyncio
async def test_metadata_structure_validation(async_session, async_client):
    """Verify misconception metadata JSON structure."""
    # Login and create session
    await async_client.post(
        "/login",
        data={
            "username": "test_teacher",
            "password": "test1234",
        },
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    # Mock analysis with all expected fields
    mock_analysis = {
        "maintains_misconception": False,
        "misconception_strength": 0.3,
        "evidence": "Student showing signs of correction",
        "drift_detected": True,
        "analysis_notes": "Misconception weakening",
    }

    with (
        patch("src.services.session_mgr.StudentBot") as MockStudentBot,
        patch("src.services.session_mgr.MisconceptionAnalyzer") as MockAnalyzer,
    ):
        MockStudentBot.return_value = _make_student_bot_mock()

        mock_analyzer_instance = AsyncMock()
        mock_analyzer_instance.analyze_student_response = AsyncMock(
            return_value=mock_analysis
        )
        MockAnalyzer.return_value = mock_analyzer_instance

        # Send message
        resp = await async_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Can you explain further?"},
        )
        assert resp.status_code == 200

    # Get student message
    result = await async_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.role == "student")
    )
    student_msg = result.scalar_one()

    # Parse and validate metadata structure
    analysis = json.loads(student_msg.analysis_metadata)

    # Verify all required fields
    required_fields = [
        "maintains_misconception",
        "misconception_strength",
        "evidence",
        "drift_detected",
        "analysis_notes",
    ]
    for field in required_fields:
        assert field in analysis, f"Missing required field: {field}"

    # Verify field types
    assert isinstance(analysis["maintains_misconception"], bool)
    assert isinstance(analysis["misconception_strength"], (int, float))
    assert isinstance(analysis["evidence"], str)
    assert isinstance(analysis["drift_detected"], bool)
    assert isinstance(analysis["analysis_notes"], str)

    # Verify value ranges
    assert 0.0 <= analysis["misconception_strength"] <= 1.0


@pytest.mark.asyncio
async def test_misconception_analysis_failure_graceful_degradation(
    async_session, async_client
):
    """Verify dialogue continues if analysis fails."""
    # Login and create session
    await async_client.post(
        "/login",
        data={
            "username": "test_teacher",
            "password": "test1234",
        },
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    with (
        patch("src.services.session_mgr.StudentBot") as MockStudentBot,
        patch("src.services.session_mgr.MisconceptionAnalyzer") as MockAnalyzer,
    ):
        MockStudentBot.return_value = _make_student_bot_mock()

        # Mock analyzer to raise exception
        mock_analyzer_instance = AsyncMock()
        mock_analyzer_instance.analyze_student_response = AsyncMock(
            side_effect=Exception("API error")
        )
        MockAnalyzer.return_value = mock_analyzer_instance

        # Send message - should not fail
        msg_response = await async_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "What do you think?"},
        )

        # Response should still succeed
        assert msg_response.status_code == 200

    # Verify student message created without metadata
    result = await async_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.role == "student")
    )
    student_msg = result.scalar_one()

    # Metadata should be None or empty
    assert (
        student_msg.analysis_metadata is None
        or student_msg.analysis_metadata == ""
    )


@pytest.mark.asyncio
async def test_session_analysis_includes_scenario_context(
    async_session, async_client
):
    """Verify scenario context passed to session analysis."""
    # Login and create session
    await async_client.post(
        "/login",
        data={
            "username": "test_teacher",
            "password": "test1234",
        },
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    with (
        patch("src.services.session_mgr.StudentBot") as MockStudentBot,
        patch(
            "src.services.session_mgr.MisconceptionAnalyzer"
        ) as MockMisAnalyzer,
    ):
        MockStudentBot.return_value = _make_student_bot_mock()

        mock_mis = AsyncMock()
        mock_mis.analyze_student_response = AsyncMock(
            return_value={
                "maintains_misconception": True,
                "misconception_strength": 0.8,
                "evidence": "Test",
                "drift_detected": False,
                "analysis_notes": "Test",
            }
        )
        MockMisAnalyzer.return_value = mock_mis

        # Send teacher messages
        for q in ["Question 1", "Question 2"]:
            await async_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": q},
            )

    # End session
    end_response = await async_client.post(f"/sessions/{session_id}/end")
    assert end_response.status_code == 200

    # Mock analyze_session for the /analyze call and
    # verify it is called with the correct scenario
    with patch(
        "src.api.routes.session_analysis.analyze_session"
    ) as mock_analyze:
        mock_analyze.return_value = {
            "distribution": {
                "high_leverage": 1,
                "medium_leverage": 1,
                "low_leverage": 0,
            },
            "feedback": "Good technique.",
        }

        analyze_response = await async_client.post(
            f"/sessions/{session_id}/analyze"
        )
        assert analyze_response.status_code == 200
        data = analyze_response.json()
        assert "distribution" in data
        assert "feedback" in data

        # Verify analyze_session was called
        assert mock_analyze.called
        # scenario is the 3rd positional arg (index 2)
        called_scenario = mock_analyze.call_args[0][2]
        assert called_scenario.title == ("Misconception Test Scenario")
        assert called_scenario.prompt is not None


@pytest.mark.asyncio
async def test_multiple_student_responses_all_analyzed(
    async_session, async_client
):
    """Verify all student responses are analyzed."""
    # Login and create session
    await async_client.post(
        "/login",
        data={
            "username": "test_teacher",
            "password": "test1234",
        },
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    # Track analysis calls
    analysis_calls = []

    async def create_mock_analysis(*args, **kwargs):
        analysis_calls.append(kwargs)
        return {
            "maintains_misconception": True,
            "misconception_strength": 0.7,
            "evidence": f"Analysis {len(analysis_calls)}",
            "drift_detected": False,
            "analysis_notes": "Test",
        }

    with (
        patch("src.services.session_mgr.StudentBot") as MockStudentBot,
        patch("src.services.session_mgr.MisconceptionAnalyzer") as MockAnalyzer,
    ):
        MockStudentBot.return_value = _make_student_bot_mock()

        mock_instance = AsyncMock()
        mock_instance.analyze_student_response = AsyncMock(
            side_effect=create_mock_analysis
        )
        MockAnalyzer.return_value = mock_instance

        # Send 3 teacher messages
        for i in range(3):
            resp = await async_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": f"Question {i + 1}"},
            )
            assert resp.status_code == 200

    # Verify all 3 student responses were analyzed
    assert len(analysis_calls) == 3

    # Verify all student messages have metadata
    result = await async_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.role == "student")
        .order_by(Message.created_at)
    )
    student_messages = result.scalars().all()

    assert len(student_messages) == 3

    for i, msg in enumerate(student_messages):
        assert msg.analysis_metadata is not None
        analysis = json.loads(msg.analysis_metadata)
        assert analysis["evidence"] == f"Analysis {i + 1}"
