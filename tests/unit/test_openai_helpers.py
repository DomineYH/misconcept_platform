"""
Unit tests for OpenAI Responses API helper utilities.
"""

from unittest.mock import Mock

import pytest

from src.utils.openai_helpers import (
    IncompleteResponseError,
    extract_response_text,
    extract_usage_dict,
)


def create_nested_response(content: str) -> Mock:
    """Create Responses API-like mock with nested content blocks."""
    text_payload = Mock()
    text_payload.value = content

    content_block = Mock()
    content_block.type = "output_text"
    content_block.text = text_payload

    output_item = Mock()
    output_item.content = [content_block]

    response = Mock()
    response.output = [output_item]
    response.output_text = None
    return response


def test_extract_response_text_nested_blocks():
    """It should read the first nested text block."""
    response = create_nested_response("Nested text payload")

    result = extract_response_text(response)

    assert result == "Nested text payload"


def test_extract_response_text_output_text_list():
    """It should fall back to output_text helper list."""
    response = Mock()
    response.output = None
    response.output_text = ["First chunk ", " Second chunk"]

    result = extract_response_text(response)

    assert result == "First chunk\nSecond chunk"


def test_extract_response_text_simple_string_content():
    """It should handle simple output.content strings."""
    output_mock = Mock()
    output_mock.content = "   Simple text body   "

    response = Mock()
    response.output = output_mock
    response.output_text = None

    result = extract_response_text(response)

    assert result == "Simple text body"


def test_extract_response_text_missing_content():
    """It should raise when no textual payload is present."""
    response = Mock()
    response.output = []
    response.output_text = None

    with pytest.raises(ValueError):
        extract_response_text(response)


def test_extract_response_text_incomplete_returns_partial():
    """Incomplete responses should still return whatever text exists."""
    response = Mock()
    response.status = "incomplete"
    response.incomplete_details = {"reason": "max_output_tokens"}
    response.output = None
    response.output_text = "Partial tutor feedback"

    result = extract_response_text(response)

    assert result == "Partial tutor feedback"


def test_extract_usage_dict_supports_response_objects():
    """Responses API usage objects are normalized to legacy token keys."""
    usage = Mock()
    usage.input_tokens = 11
    usage.output_tokens = 7
    usage.total_tokens = 18
    response = Mock()
    response.usage = usage

    result = extract_usage_dict(response)

    assert result == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }


def test_extract_usage_dict_supports_dicts():
    """Mock and serialized usage dictionaries are accepted."""
    response = Mock()
    response.usage = {
        "input_tokens": 5,
        "output_tokens": 3,
        "total_tokens": 8,
    }

    result = extract_usage_dict(response)

    assert result == {
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }


def test_extract_response_text_incomplete_without_text_raises_typed_error():
    """Incomplete responses without visible text should expose the reason."""
    response = Mock()
    response.status = "incomplete"
    response.incomplete_details = {"reason": "max_output_tokens"}
    response.output = []
    response.output_text = None

    with pytest.raises(IncompleteResponseError) as exc:
        extract_response_text(response)

    assert exc.value.reason == "max_output_tokens"
    assert "max_output_tokens" in str(exc.value)


def test_extract_usage_dict_includes_reasoning_tokens_from_object_details():
    """Responses usage details should preserve reasoning token count."""
    details = Mock()
    details.reasoning_tokens = 64
    usage = Mock()
    usage.input_tokens = 100
    usage.output_tokens = 80
    usage.total_tokens = 180
    usage.output_tokens_details = details
    response = Mock()
    response.usage = usage

    result = extract_usage_dict(response)

    assert result == {
        "prompt_tokens": 100,
        "completion_tokens": 80,
        "total_tokens": 180,
        "reasoning_tokens": 64,
    }


def test_extract_usage_dict_includes_reasoning_tokens_from_dict_details():
    """Serialized usage details should preserve reasoning token count."""
    response = Mock()
    response.usage = {
        "input_tokens": 20,
        "output_tokens": 12,
        "total_tokens": 32,
        "output_tokens_details": {"reasoning_tokens": 9},
    }

    result = extract_usage_dict(response)

    assert result == {
        "prompt_tokens": 20,
        "completion_tokens": 12,
        "total_tokens": 32,
        "reasoning_tokens": 9,
    }
