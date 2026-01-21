"""
Unit tests for OpenAI Responses API helper utilities.
"""

from unittest.mock import Mock

import pytest

from src.utils.openai_helpers import extract_response_text


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
