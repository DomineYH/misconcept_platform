"""Integration tests for misconception tracking and analysis."""
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from sqlalchemy import select

from src.models import Message, QuestionAnalysis
from src.services.session_mgr import SessionManager


@pytest.mark.asyncio
async def test_student_response_analyzed_for_misconception(
    async_session, async_client
):
    """학생 응답에 오개념 분석이 수행되고 metadata에 저장되는지 검증."""
    # Login
    login_response = await async_client.post(
        "/login",
        data={"username": "test_teacher", "password": "test1234"},
    )
    assert login_response.status_code == 303

    # Create session
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    assert session_response.status_code == 201
    session_data = session_response.json()
    session_id = session_data["id"]

    # Mock MisconceptionAnalyzer response
    mock_analysis = {
        "maintains_misconception": True,
        "misconception_strength": 0.85,
        "evidence": "Student clearly maintains the misconception",
        "drift_detected": False,
        "analysis_notes": "Strong adherence observed",
    }

    with patch(
        "src.services.session_mgr.MisconceptionAnalyzer"
    ) as MockAnalyzer:
        mock_instance = MockAnalyzer.return_value
        mock_instance.analyze_student_response = AsyncMock(
            return_value=mock_analysis
        )

        # Send teacher message
        msg_response = await async_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Why do you think that?"},
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
    assert student_msg.metadata is not None
    analysis = json.loads(student_msg.metadata)

    assert "maintains_misconception" in analysis
    assert "misconception_strength" in analysis
    assert analysis["maintains_misconception"] is True
    assert 0.0 <= analysis["misconception_strength"] <= 1.0
    assert "evidence" in analysis


@pytest.mark.asyncio
async def test_metadata_structure_validation(async_session, async_client):
    """오개념 분석 metadata의 JSON 구조가 올바른지 검증."""
    # Login and create session
    await async_client.post(
        "/login",
        data={"username": "test_teacher", "password": "test1234"},
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    session_id = session_response.json()["id"]

    # Mock analysis with all expected fields
    mock_analysis = {
        "maintains_misconception": False,
        "misconception_strength": 0.3,
        "evidence": "Student showing signs of correction",
        "drift_detected": True,
        "analysis_notes": "Misconception weakening",
    }

    with patch(
        "src.services.session_mgr.MisconceptionAnalyzer"
    ) as MockAnalyzer:
        mock_instance = MockAnalyzer.return_value
        mock_instance.analyze_student_response = AsyncMock(
            return_value=mock_analysis
        )

        # Send message
        await async_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Can you explain further?"},
        )

    # Get student message
    result = await async_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.role == "student")
    )
    student_msg = result.scalar_one()

    # Parse and validate metadata structure
    analysis = json.loads(student_msg.metadata)

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
    """오개념 분석 실패 시 대화 흐름이 유지되는지 검증."""
    # Login and create session
    await async_client.post(
        "/login",
        data={"username": "test_teacher", "password": "test1234"},
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    session_id = session_response.json()["id"]

    # Mock analyzer to raise exception
    with patch(
        "src.services.session_mgr.MisconceptionAnalyzer"
    ) as MockAnalyzer:
        mock_instance = MockAnalyzer.return_value
        mock_instance.analyze_student_response = AsyncMock(
            side_effect=Exception("API error")
        )

        # Send message - should not fail despite analyzer error
        msg_response = await async_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "What do you think?"},
        )

        # Response should still succeed
        assert msg_response.status_code == 200

    # Verify student message was created without metadata
    result = await async_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.role == "student")
    )
    student_msg = result.scalar_one()

    # Metadata should be None or empty due to analysis failure
    assert student_msg.metadata is None or student_msg.metadata == ""


@pytest.mark.asyncio
async def test_session_analysis_includes_scenario_context(
    async_session, async_client
):
    """세션 종료 분석 시 시나리오 정보가 포함되는지 검증."""
    # Login and create session
    await async_client.post(
        "/login",
        data={"username": "test_teacher", "password": "test1234"},
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    session_id = session_response.json()["id"]

    # Mock MisconceptionAnalyzer for student messages
    with patch(
        "src.services.session_mgr.MisconceptionAnalyzer"
    ) as MockMisAnalyzer:
        mock_mis_instance = MockMisAnalyzer.return_value
        mock_mis_instance.analyze_student_response = AsyncMock(
            return_value={
                "maintains_misconception": True,
                "misconception_strength": 0.8,
                "evidence": "Test",
                "drift_detected": False,
                "analysis_notes": "Test",
            }
        )

        # Send multiple teacher messages
        await async_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Question 1"},
        )
        await async_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Question 2"},
        )

    # Mock Analyzer for session end analysis
    with patch("src.services.analyzer.Analyzer") as MockAnalyzer:
        mock_instance = Mock()

        # Capture classify_question calls
        calls = []

        async def mock_classify(
            question,
            framework,
            context=None,
            scenario_title=None,
            misconception_prompt=None,
            student_profile=None,
        ):
            calls.append(
                {
                    "question": question,
                    "scenario_title": scenario_title,
                    "misconception_prompt": misconception_prompt,
                    "student_profile": student_profile,
                }
            )
            return {
                "label": "Pressing",
                "confidence": 0.9,
                "reasoning": "Test reasoning",
            }

        mock_instance.classify_question = mock_classify
        MockAnalyzer.return_value = mock_instance

        # End session
        end_response = await async_client.post(
            f"/sessions/{session_id}/end"
        )

        assert end_response.status_code == 200

        # Verify classify_question was called with scenario context
        assert len(calls) >= 2  # At least 2 teacher questions

        for call in calls:
            # Verify scenario context parameters were provided
            assert call["scenario_title"] is not None
            assert call["misconception_prompt"] is not None
            assert call["student_profile"] is not None

            # Verify they contain actual values, not just "Not specified"
            assert call["scenario_title"] != "Not specified"
            assert call["misconception_prompt"] != "Not specified"


@pytest.mark.asyncio
async def test_multiple_student_responses_all_analyzed(
    async_session, async_client
):
    """여러 학생 응답이 모두 분석되는지 검증."""
    # Login and create session
    await async_client.post(
        "/login",
        data={"username": "test_teacher", "password": "test1234"},
    )
    session_response = await async_client.post(
        "/sessions", json={"scenario_id": 1}
    )
    session_id = session_response.json()["id"]

    # Track analysis calls
    analysis_calls = []

    def create_mock_analysis(*args, **kwargs):
        analysis_calls.append(kwargs)
        return {
            "maintains_misconception": True,
            "misconception_strength": 0.7,
            "evidence": f"Analysis {len(analysis_calls)}",
            "drift_detected": False,
            "analysis_notes": "Test",
        }

    with patch(
        "src.services.session_mgr.MisconceptionAnalyzer"
    ) as MockAnalyzer:
        mock_instance = MockAnalyzer.return_value
        mock_instance.analyze_student_response = AsyncMock(
            side_effect=create_mock_analysis
        )

        # Send 3 teacher messages
        for i in range(3):
            await async_client.post(
                f"/sessions/{session_id}/messages",
                json={"content": f"Question {i+1}"},
            )

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
        assert msg.metadata is not None
        analysis = json.loads(msg.metadata)
        assert analysis["evidence"] == f"Analysis {i+1}"
