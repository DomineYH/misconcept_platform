"""Unit tests for session_feedback utility functions (E7)."""

from src.services.session_synthesizer import (
    FALLBACK_FEEDBACK,
)
from src.utils.session_feedback import (
    derive_plain_feedback,
)


class TestDerivePlainFeedback:
    """Tests for derive_plain_feedback()."""

    def test_extracts_first_brief_feedback(self):
        payload = {
            "brief_feedback": [
                "좋은 탐색 질문이었어요!",
                "두 번째 문장.",
            ]
        }
        result = derive_plain_feedback(payload)
        assert result == "좋은 탐색 질문이었어요!"

    def test_rejects_json_looking_brace(self):
        payload = {
            "brief_feedback": [
                '{"key": "value"}',
            ]
        }
        result = derive_plain_feedback(payload)
        assert result == FALLBACK_FEEDBACK

    def test_rejects_json_looking_bracket(self):
        payload = {
            "brief_feedback": [
                '["item1", "item2"]',
            ]
        }
        result = derive_plain_feedback(payload)
        assert result == FALLBACK_FEEDBACK

    def test_empty_brief_feedback_returns_fallback(self):
        result = derive_plain_feedback({"brief_feedback": []})
        assert result == FALLBACK_FEEDBACK

    def test_no_brief_feedback_key_returns_fallback(self):
        result = derive_plain_feedback({})
        assert result == FALLBACK_FEEDBACK

    def test_null_brief_feedback_returns_fallback(self):
        result = derive_plain_feedback({"brief_feedback": None})
        assert result == FALLBACK_FEEDBACK

    def test_clamps_to_500_chars(self):
        long_text = "가" * 600
        payload = {"brief_feedback": [long_text]}
        result = derive_plain_feedback(payload)
        assert len(result) <= 500

    def test_whitespace_normalized(self):
        payload = {
            "brief_feedback": [
                "  hello   world  ",
            ]
        }
        result = derive_plain_feedback(payload)
        assert result == "hello world"

    def test_non_string_item_returns_fallback(self):
        payload = {"brief_feedback": [123]}
        result = derive_plain_feedback(payload)
        assert result == FALLBACK_FEEDBACK

    def test_empty_string_returns_fallback(self):
        payload = {"brief_feedback": [""]}
        result = derive_plain_feedback(payload)
        assert result == FALLBACK_FEEDBACK

    def test_whitespace_only_returns_fallback(self):
        payload = {"brief_feedback": ["   "]}
        result = derive_plain_feedback(payload)
        assert result == FALLBACK_FEEDBACK
