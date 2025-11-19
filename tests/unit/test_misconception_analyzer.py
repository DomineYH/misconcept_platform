"""
Unit tests for MisconceptionAnalyzer service.

Tests misconception analysis with mocked OpenAI responses.
"""
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.services.misconception_analyzer import MisconceptionAnalyzer


@pytest.fixture
async def analyzer(db_session):
    """Create analyzer instance with mocked OpenAI client."""
    with patch("src.services.misconception_analyzer.AsyncOpenAI") as mock_client:
        analyzer = MisconceptionAnalyzer(db_session=db_session)
        analyzer.client = mock_client.return_value
        return analyzer


@pytest.mark.asyncio
async def test_analyze_student_response_valid_json(analyzer):
    """Test successful analysis with valid JSON response."""
    # Mock OpenAI response
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=json.dumps({
                    "maintains_misconception": True,
                    "misconception_strength": 0.85,
                    "evidence": "Student clearly states moon makes its own light",
                    "drift_detected": False,
                    "analysis_notes": "Strong adherence to misconception"
                })
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Analyze student response
    result = await analyzer.analyze_student_response(
        student_message="The moon shines because it makes its own light.",
        scenario_prompt="Moon is a light source",
        student_profile="Grade 5 student",
        scenario_title="Moon Phases Misconception",
    )

    # Verify result structure
    assert result["maintains_misconception"] is True
    assert result["misconception_strength"] == 0.85
    assert "evidence" in result
    assert result["drift_detected"] is False
    assert "analysis_notes" in result


@pytest.mark.asyncio
async def test_analyze_student_response_json_in_code_block(analyzer):
    """Test parsing JSON wrapped in markdown code block."""
    # Mock response with JSON in code block
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='```json\n{\n  "maintains_misconception": false,\n  '
                        '"misconception_strength": 0.2,\n  '
                        '"evidence": "Student corrected understanding",\n  '
                        '"drift_detected": true,\n  '
                        '"analysis_notes": "Student showing signs of correction"\n}\n```'
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Analyze student response
    result = await analyzer.analyze_student_response(
        student_message="The moon reflects light from the sun.",
        scenario_prompt="Moon is a light source",
        student_profile="Grade 5 student",
        scenario_title="Moon Phases Misconception",
    )

    # Verify parsing worked
    assert result["maintains_misconception"] is False
    assert result["misconception_strength"] == 0.2
    assert result["drift_detected"] is True


@pytest.mark.asyncio
async def test_analyze_student_response_strength_range(analyzer):
    """Test misconception strength is within valid range."""
    # Mock response
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=json.dumps({
                    "maintains_misconception": True,
                    "misconception_strength": 0.75,
                    "evidence": "Test evidence",
                    "drift_detected": False,
                    "analysis_notes": "Test notes"
                })
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Analyze
    result = await analyzer.analyze_student_response(
        student_message="Test message",
        scenario_prompt="Test prompt",
        student_profile="Test profile",
        scenario_title="Test scenario",
    )

    # Verify strength is in valid range
    assert 0.0 <= result["misconception_strength"] <= 1.0


@pytest.mark.asyncio
async def test_analyze_student_response_invalid_json(analyzer):
    """Test handling of invalid JSON response with fallback."""
    # Mock response with invalid JSON
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content="This is not valid JSON at all"
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Analyze - should not raise, should return default values
    result = await analyzer.analyze_student_response(
        student_message="Test message",
        scenario_prompt="Test prompt",
        student_profile="Test profile",
        scenario_title="Test scenario",
    )

    # Verify default fallback values
    assert "maintains_misconception" in result
    assert "misconception_strength" in result
    assert result["misconception_strength"] == 0.5  # Default
    assert "Parse error" in result["evidence"]


@pytest.mark.asyncio
async def test_analyze_student_response_missing_fields(analyzer):
    """Test handling of response missing some fields."""
    # Mock response missing drift_detected field
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=json.dumps({
                    "maintains_misconception": True,
                    "misconception_strength": 0.6,
                    "evidence": "Test evidence"
                    # Missing drift_detected and analysis_notes
                })
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Analyze
    result = await analyzer.analyze_student_response(
        student_message="Test message",
        scenario_prompt="Test prompt",
        student_profile="Test profile",
        scenario_title="Test scenario",
    )

    # Verify default values are provided for missing fields
    assert result["maintains_misconception"] is True
    assert result["misconception_strength"] == 0.6
    assert result["evidence"] == "Test evidence"
    assert result["drift_detected"] is False  # Default
    assert "analysis_notes" in result  # Should have default


@pytest.mark.asyncio
async def test_analyze_student_response_builds_correct_prompt(analyzer):
    """Test that analysis prompt includes all scenario context."""
    # Mock response
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=json.dumps({
                    "maintains_misconception": True,
                    "misconception_strength": 0.8,
                    "evidence": "Test",
                    "drift_detected": False,
                    "analysis_notes": "Test"
                })
            )
        )
    ]

    # Capture the API call
    create_mock = AsyncMock(return_value=mock_response)
    analyzer.client.chat.completions.create = create_mock

    # Analyze
    await analyzer.analyze_student_response(
        student_message="The moon glows bright.",
        scenario_prompt="Moon is a light source",
        student_profile="Grade 5 student",
        scenario_title="Moon Phases",
    )

    # Verify API was called with correct parameters
    create_mock.assert_called_once()
    call_args = create_mock.call_args

    # Check messages structure
    messages = call_args.kwargs["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "Moon Phases" in messages[0]["content"]
    assert "Moon is a light source" in messages[0]["content"]
    assert "Grade 5 student" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "The moon glows bright" in messages[1]["content"]


@pytest.mark.asyncio
async def test_analyze_student_response_low_temperature(analyzer):
    """Test that analyzer uses low temperature for consistency."""
    # Mock response
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=json.dumps({
                    "maintains_misconception": False,
                    "misconception_strength": 0.3,
                    "evidence": "Test",
                    "drift_detected": True,
                    "analysis_notes": "Test"
                })
            )
        )
    ]

    create_mock = AsyncMock(return_value=mock_response)
    analyzer.client.chat.completions.create = create_mock

    # Analyze
    await analyzer.analyze_student_response(
        student_message="Test",
        scenario_prompt="Test",
        student_profile="Test",
        scenario_title="Test",
    )

    # Verify temperature is 0.3 (low for consistency)
    call_args = create_mock.call_args
    assert call_args.kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_analyze_student_response_type_conversions(analyzer):
    """Test that string values are properly converted to types."""
    # Mock response with string values
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=json.dumps({
                    "maintains_misconception": "true",  # String instead of bool
                    "misconception_strength": "0.95",   # String instead of float
                    "evidence": "Strong evidence",
                    "drift_detected": "false",
                    "analysis_notes": "Notes"
                })
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Analyze
    result = await analyzer.analyze_student_response(
        student_message="Test",
        scenario_prompt="Test",
        student_profile="Test",
        scenario_title="Test",
    )

    # Verify types are correct (parser should handle conversion)
    assert isinstance(result["misconception_strength"], float)
    assert result["misconception_strength"] == 0.95
