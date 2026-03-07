"""
Unit tests for Analyzer service (T061).

Tests question classification with mocked OpenAI responses.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.analysis_framework import AnalysisFramework
from src.services.analyzer import Analyzer


@pytest.fixture
def mock_framework():
    """Create test analysis framework."""
    framework = Mock(spec=AnalysisFramework)
    framework.name = "High/Low Leverage"
    framework.description = "Test framework"
    framework.labels = [
        {"name": "Pressing", "criteria": "학생의 사고를 깊이 탐색하는 질문"},
        {"name": "Linking", "criteria": "아이디어를 연결하는 안내형 질문"},
        {"name": "Directing", "criteria": "방향을 제시하는 질문"},
        {"name": "Recall", "criteria": "단순 사실 확인 질문"},
    ]
    framework.label_names = [
        "Pressing",
        "Linking",
        "Directing",
        "Recall",
    ]
    framework.label_criteria_map = {
        "Pressing": "학생의 사고를 깊이 탐색하는 질문",
        "Linking": "아이디어를 연결하는 안내형 질문",
        "Directing": "방향을 제시하는 질문",
        "Recall": "단순 사실 확인 질문",
    }
    return framework


@pytest.fixture
def analyzer():
    """Create analyzer instance with mocked OpenAI client."""
    with patch("src.services.analyzer.AsyncOpenAI") as mock_client:
        analyzer = Analyzer()
        analyzer.client = mock_client.return_value
        return analyzer


@pytest.mark.asyncio
async def test_classify_question_valid_response(analyzer, mock_framework):
    """Test successful classification with valid response."""
    # Mock OpenAI Responses API response
    mock_response = Mock()
    mock_response.output = Mock(
        content='{"label": "Pressing", '
        '"confidence": 0.92, '
        '"reasoning": "Encourages articulation"}'
    )
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

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
    # Mock Responses API response with invalid label
    mock_response = Mock()
    mock_response.output = Mock(
        content='{"label": "InvalidLabel", "confidence": 0.8}'
    )
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Classify question
    result = await analyzer.classify_question("Test question?", mock_framework)

    # Should use first framework label
    assert result["label"] == "Pressing"


@pytest.mark.asyncio
async def test_classify_question_confidence_range(analyzer, mock_framework):
    """Test confidence score is clamped to [0, 1]."""
    # Mock Responses API response with out-of-range confidence
    mock_response = Mock()
    mock_response.output = Mock(
        content='{"label": "Recall", "confidence": 1.5}'
    )
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Classify question
    result = await analyzer.classify_question("What is 2+2?", mock_framework)

    # Confidence should be clamped
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_classify_question_json_error(analyzer, mock_framework):
    """Test handling of invalid JSON response."""
    # Mock Responses API response with invalid JSON
    mock_response = Mock()
    mock_response.output = Mock(content="Not valid JSON")
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Should raise ValueError
    with pytest.raises(ValueError, match="Invalid JSON"):
        await analyzer.classify_question("Test question?", mock_framework)


@pytest.mark.asyncio
async def test_classify_question_missing_fields(analyzer, mock_framework):
    """Test handling of response missing required fields."""
    # Mock Responses API response missing confidence field
    mock_response = Mock()
    mock_response.output = Mock(content='{"label": "Recall"}')
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Should raise ValueError
    with pytest.raises(ValueError, match="missing required fields"):
        await analyzer.classify_question("Test question?", mock_framework)


@pytest.mark.asyncio
async def test_batch_classify_multiple_questions(analyzer, mock_framework):
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
        response.output = Mock(content=mock_responses[call_count])
        call_count += 1
        return response

    analyzer.client.responses.create = mock_create

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
async def test_batch_classify_handles_failures(analyzer, mock_framework):
    """Test batch classification continues on individual failures."""
    # Mock responses with one failure
    call_count = 0

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("API error")
        response = Mock()
        response.output = Mock(
            content='{"label": "Pressing", "confidence": 0.9}'
        )
        return response

    analyzer.client.responses.create = mock_create

    # Batch classify
    questions = ["Q1?", "Q2?", "Q3?"]
    results = await analyzer.batch_classify(questions, mock_framework)

    # Should have 3 results with default for failed one
    assert len(results) == 3
    assert results[1]["confidence"] == 0.0  # Failed classification
    assert "failed" in results[1]["reasoning"].lower()


@pytest.mark.asyncio
async def test_detect_greetings_empty_list(analyzer):
    """Test detection with empty message list."""
    result = await analyzer.detect_greetings([])
    assert result == []


@pytest.mark.asyncio
async def test_detect_greetings_valid_response(analyzer):
    """Test successful greeting detection."""
    # Mock Responses API response
    mock_response = Mock()
    mock_response.output = Mock(
        content=(
            '[{"index": 0, "is_greeting": true,'
            ' "reason": "Opening greeting"}, '
            '{"index": 1, "is_greeting": false,'
            ' "reason": "Question about concept"}]'
        )
    )
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Detect greetings
    messages = [
        "안녕하세요!",
        "분수의 덧셈에서 분모가 다르면 어떻게 해야 할까요?",
    ]
    results = await analyzer.detect_greetings(messages)

    # Verify results
    assert len(results) == 2
    assert results[0]["is_greeting"] is True
    assert results[1]["is_greeting"] is False


@pytest.mark.asyncio
async def test_detect_greetings_returns_safe_default_on_json_error(analyzer):
    """Test that JSON parse error returns safe defaults."""
    # Mock Responses API response with invalid JSON
    mock_response = Mock()
    mock_response.output = Mock(content="Not valid JSON")
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Detect greetings
    messages = ["안녕하세요!", "질문입니다"]
    results = await analyzer.detect_greetings(messages)

    # Should return safe defaults (no greetings)
    assert len(results) == 2
    assert results[0]["is_greeting"] is False
    assert results[1]["is_greeting"] is False


@pytest.mark.asyncio
async def test_detect_greetings_returns_safe_default_on_api_error(analyzer):
    """Test that API error returns safe defaults after retries."""
    # Mock API to raise exception
    analyzer.client.responses.create = AsyncMock(
        side_effect=Exception("API error")
    )

    # Detect greetings (will retry 3 times then fail gracefully)
    messages = ["안녕하세요!", "질문입니다"]

    # Should not raise, should return safe defaults
    results = await analyzer.detect_greetings(messages)

    assert len(results) == 2
    assert results[0]["is_greeting"] is False
    assert results[1]["is_greeting"] is False


@pytest.mark.asyncio
async def test_detect_greetings_fills_missing_indices(analyzer):
    """Test that missing indices are filled with defaults."""
    # Mock response with only one index
    mock_response = Mock()
    mock_response.output = Mock(
        content='[{"index": 0, "is_greeting": true, "reason": "Greeting"}]'
    )
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Detect greetings for 3 messages
    messages = ["안녕!", "질문1", "질문2"]
    results = await analyzer.detect_greetings(messages)

    # Should have 3 results with defaults for missing ones
    assert len(results) == 3
    assert results[0]["is_greeting"] is True
    assert results[1]["is_greeting"] is False  # Default
    assert results[2]["is_greeting"] is False  # Default


# ============================================================
# Structured Reasoning Tests (Enhanced Analysis)
# ============================================================


@pytest.mark.asyncio
async def test_classify_question_structured_reasoning(analyzer, mock_framework):
    """Test successful classification with full structured reasoning."""
    import json

    structured_response = {
        "label": "Pressing",
        "confidence": 0.92,
        "reasoning": {
            "summary": "학생이 자신의 사고 모델을 표현하도록 유도하는 질문",
            "pedagogical": {
                "educational_principle": "구성주의",
                "effectiveness": "높음 - 능동적 지식 구성 촉진",
                "improvement_suggestion": None,
            },
            "cognitive": {
                "cognitive_demand": "분석",
                "student_response_prediction": "학생이 추론을 설명함",
                "misconception_addressing": "오개념을 직접적으로 탐색",
            },
            "contextual": {
                "dialogue_role": "탐색 질문",
                "timing_appropriateness": "적절함",
                "connection_to_prior": "이전 논의와 연결됨",
            },
        },
    }

    mock_response = Mock()
    mock_response.output = Mock(content=json.dumps(structured_response))
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Classify question
    result = await analyzer.classify_question(
        "왜 그렇게 생각하나요?",
        mock_framework,
        context="학생이 잘못된 진술을 했음",
    )

    # Verify structure
    assert result["label"] == "Pressing"
    assert result["confidence"] == 0.92
    assert isinstance(result["reasoning"], dict)
    assert "summary" in result["reasoning"]
    assert "pedagogical" in result["reasoning"]
    assert "cognitive" in result["reasoning"]
    assert "contextual" in result["reasoning"]

    # Verify pedagogical content
    ped = result["reasoning"]["pedagogical"]
    assert ped["educational_principle"] == "구성주의"
    assert ped["effectiveness"] == "높음 - 능동적 지식 구성 촉진"

    # Verify cognitive content
    cog = result["reasoning"]["cognitive"]
    assert cog["cognitive_demand"] == "분석"

    # Verify contextual content
    ctx = result["reasoning"]["contextual"]
    assert ctx["dialogue_role"] == "탐색 질문"


@pytest.mark.asyncio
async def test_classify_question_legacy_reasoning_compatibility(
    analyzer, mock_framework
):
    """Test backward compatibility with simple string reasoning."""
    import json

    legacy_response = {
        "label": "Pressing",
        "confidence": 0.85,
        "reasoning": "학생의 표현을 유도하는 질문",
    }

    mock_response = Mock()
    mock_response.output = Mock(content=json.dumps(legacy_response))
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Classify question
    result = await analyzer.classify_question(
        "테스트 질문?",
        mock_framework,
    )

    # Should handle legacy format gracefully
    assert result["label"] == "Pressing"
    assert "reasoning" in result

    # Reasoning should be normalized to dict
    reasoning = result["reasoning"]
    assert isinstance(reasoning, dict)
    assert reasoning["summary"] == "학생의 표현을 유도하는 질문"
    assert reasoning["pedagogical"] is None
    assert reasoning["cognitive"] is None
    assert reasoning["contextual"] is None


@pytest.mark.asyncio
async def test_classify_question_partial_reasoning(analyzer, mock_framework):
    """Test handling of partial reasoning structure."""
    import json

    partial_response = {
        "label": "Linking",
        "confidence": 0.88,
        "reasoning": {
            "summary": "개념을 연결하는 질문",
            "pedagogical": {
                "educational_principle": "비계 설정",
                "effectiveness": "중간",
                "improvement_suggestion": None,
            },
            # cognitive and contextual missing
        },
    }

    mock_response = Mock()
    mock_response.output = Mock(content=json.dumps(partial_response))
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    # Classify question
    result = await analyzer.classify_question(
        "어떻게 연결되나요?",
        mock_framework,
    )

    # Should handle partial structure
    assert result["label"] == "Linking"
    assert result["reasoning"]["summary"] == "개념을 연결하는 질문"
    assert result["reasoning"]["pedagogical"] is not None
    assert result["reasoning"]["cognitive"] is None
    assert result["reasoning"]["contextual"] is None


def test_normalize_reasoning_with_string(analyzer):
    """Test _normalize_reasoning with legacy string format."""
    result = analyzer._normalize_reasoning("간단한 분석")

    assert isinstance(result, dict)
    assert result["summary"] == "간단한 분석"
    assert result["pedagogical"] is None
    assert result["cognitive"] is None
    assert result["contextual"] is None


def test_normalize_reasoning_with_dict(analyzer):
    """Test _normalize_reasoning with partial dict."""
    input_reasoning = {
        "summary": "요약",
        "pedagogical": {"educational_principle": "테스트"},
    }

    result = analyzer._normalize_reasoning(input_reasoning)

    assert result["summary"] == "요약"
    assert result["pedagogical"] == {"educational_principle": "테스트"}
    assert result["cognitive"] is None
    assert result["contextual"] is None


def test_normalize_reasoning_with_none(analyzer):
    """Test _normalize_reasoning with None value."""
    result = analyzer._normalize_reasoning(None)

    assert isinstance(result, dict)
    assert result["summary"] == ""
    assert result["pedagogical"] is None
    assert result["cognitive"] is None
    assert result["contextual"] is None


def test_normalize_reasoning_with_full_dict(analyzer):
    """Test _normalize_reasoning preserves full structure."""
    full_reasoning = {
        "summary": "전체 요약",
        "pedagogical": {"educational_principle": "구성주의"},
        "cognitive": {"cognitive_demand": "분석"},
        "contextual": {"dialogue_role": "탐색"},
    }

    result = analyzer._normalize_reasoning(full_reasoning)

    assert result == full_reasoning
