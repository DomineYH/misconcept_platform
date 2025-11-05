"""
Unit tests for Analyzer service (T061).

Tests question classification with mocked OpenAI responses.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.services.analyzer import Analyzer
from src.models.analysis_framework import AnalysisFramework


@pytest.fixture
def mock_framework():
    """Create test analysis framework."""
    framework = Mock(spec=AnalysisFramework)
    framework.name = "High/Low Leverage"
    framework.description = "Test framework"
    framework.labels = ["Pressing", "Linking", "Directing", "Recall"]
    return framework


@pytest.fixture
def analyzer():
    """Create analyzer instance with mocked OpenAI client."""
    with patch("src.services.analyzer.AsyncOpenAI") as mock_client:
        analyzer = Analyzer()
        analyzer.client = mock_client.return_value
        return analyzer


@pytest.mark.asyncio
async def test_classify_question_valid_response(
    analyzer, mock_framework
):
    """Test successful classification with valid response."""
    # Mock OpenAI response
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='{"label": "Pressing", '
                '"confidence": 0.92, '
                '"reasoning": "Encourages articulation"}'
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Classify question
    result = await analyzer.classify_question(
        "What happens during a solar eclipse?",
        mock_framework,
        context="Previous discussion about moon phases",
    )

    # Verify result
    assert result["label"] == "Pressing"
    assert result["confidence"] == 0.92
    assert "reasoning" in result


@pytest.mark.asyncio
async def test_classify_question_invalid_label(analyzer, mock_framework):
    """Test classification with invalid label falls back to first."""
    # Mock response with invalid label
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='{"label": "InvalidLabel", "confidence": 0.8}'
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Classify question
    result = await analyzer.classify_question(
        "Test question?", mock_framework
    )

    # Should use first framework label
    assert result["label"] == "Pressing"


@pytest.mark.asyncio
async def test_classify_question_confidence_range(
    analyzer, mock_framework
):
    """Test confidence score is clamped to [0, 1]."""
    # Mock response with out-of-range confidence
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='{"label": "Recall", "confidence": 1.5}'
            )
        )
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Classify question
    result = await analyzer.classify_question(
        "What is 2+2?", mock_framework
    )

    # Confidence should be clamped
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_classify_question_json_error(analyzer, mock_framework):
    """Test handling of invalid JSON response."""
    # Mock response with invalid JSON
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="Not valid JSON"))
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Should raise ValueError
    with pytest.raises(ValueError, match="Invalid JSON"):
        await analyzer.classify_question(
            "Test question?", mock_framework
        )


@pytest.mark.asyncio
async def test_classify_question_missing_fields(
    analyzer, mock_framework
):
    """Test handling of response missing required fields."""
    # Mock response missing confidence field
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content='{"label": "Recall"}'))
    ]
    analyzer.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Should raise ValueError
    with pytest.raises(ValueError, match="missing required fields"):
        await analyzer.classify_question(
            "Test question?", mock_framework
        )


@pytest.mark.asyncio
async def test_batch_classify_multiple_questions(
    analyzer, mock_framework
):
    """Test batch classification of multiple questions."""
    # Mock responses for each question
    mock_responses = [
        '{"label": "Pressing", "confidence": 0.9}',
        '{"label": "Linking", "confidence": 0.85}',
        '{"label": "Recall", "confidence": 0.7}',
    ]

    call_count = 0

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        response = Mock()
        response.choices = [
            Mock(message=Mock(content=mock_responses[call_count]))
        ]
        call_count += 1
        return response

    analyzer.client.chat.completions.create = mock_create

    # Batch classify
    questions = [
        "Why do you think that?",
        "How does this relate to your earlier point?",
        "What is the definition?",
    ]
    results = await analyzer.batch_classify(questions, mock_framework)

    # Verify all classified
    assert len(results) == 3
    assert results[0]["label"] == "Pressing"
    assert results[1]["label"] == "Linking"
    assert results[2]["label"] == "Recall"


@pytest.mark.asyncio
async def test_batch_classify_handles_failures(
    analyzer, mock_framework
):
    """Test batch classification continues on individual failures."""
    # Mock responses with one failure
    call_count = 0

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("API error")
        response = Mock()
        response.choices = [
            Mock(
                message=Mock(
                    content='{"label": "Pressing", "confidence": 0.9}'
                )
            )
        ]
        return response

    analyzer.client.chat.completions.create = mock_create

    # Batch classify
    questions = ["Q1?", "Q2?", "Q3?"]
    results = await analyzer.batch_classify(questions, mock_framework)

    # Should have 3 results with default for failed one
    assert len(results) == 3
    assert results[1]["confidence"] == 0.0  # Failed classification
    assert "failed" in results[1]["reasoning"].lower()
