"""Unit tests for SessionSynthesizer service (E9, E16)."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.session_synthesizer import (
    FALLBACK_FEEDBACK,
    SessionSynthesizer,
    prompt_hash,
)

MOCK_MESSAGES = [
    {"id": 1, "role": "teacher", "content": "어떻게 답을 구했어?"},
    {"id": 2, "role": "student", "content": "분자끼리 더했어요."},
    {
        "id": 3,
        "role": "teacher",
        "content": "왜 분자끼리 더해도 된다고 생각했어?",
    },
    {
        "id": 4,
        "role": "student",
        "content": "그냥 덧셈이니까요.",
    },
]

MOCK_VALID_PAYLOAD = {
    "brief_feedback": [
        "좋은 출발이었어요! 풀이 과정을 물어본 것은 훌륭했어요.",
        "다음에는 학생의 핵심 단어를 잡아보세요.",
    ],
    "strengths": [
        {
            "message_id": 1,
            "quote": "어떻게 답을 구했어?",
            "reason": "학생의 풀이 과정을 탐색했어요.",
        }
    ],
    "improvements": [
        {
            "student_message_id": 2,
            "student_quote": "분자끼리 더했어요.",
            "missed_reason": "오개념의 핵심 단서였어요.",
            "alternative_question": "왜 분모는 안 더했어?",
            "alternative_reason": "통분 개념을 유도할 수 있어요.",
        }
    ],
    "dialogue_coaching": [
        {
            "message_id": 1,
            "role": "teacher",
            "marker": "good_moment",
            "note": "좋은 탐색 질문이에요.",
        },
        {
            "message_id": 2,
            "role": "student",
            "marker": "key_clue",
            "note": "오개념 핵심 단서.",
        },
    ],
}


def _make_mock_response(payload: dict) -> Mock:
    """Create a mock Responses API response."""
    resp = Mock()
    resp.output = Mock(content=json.dumps(payload))
    resp.output_text = json.dumps(payload)
    return resp


@pytest.fixture
def mock_framework():
    """Create a mock framework."""
    fw = Mock()
    fw.name = "High/Low Leverage"
    fw.label_names = [
        "Pressing",
        "Linking",
        "Directing",
        "Recall",
    ]
    fw.label_criteria_map = {
        "Pressing": "학생의 사고를 깊이 탐색",
        "Linking": "아이디어를 연결",
        "Directing": "방향을 제시",
        "Recall": "단순 사실 확인",
    }
    return fw


@pytest.fixture
def synthesizer():
    """Create SessionSynthesizer with mocked OpenAI client."""
    with patch("src.services.session_synthesizer.AsyncOpenAI"):
        synth = SessionSynthesizer()
        synth.client = Mock()
        synth.client.responses = Mock()
        synth.client.responses.create = AsyncMock()
        return synth


class TestSessionSynthesizer:
    """Tests for SessionSynthesizer.synthesize()."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_ok(self, synthesizer, mock_framework):
        """Valid payload with all fields returns status ok."""
        mock_resp = _make_mock_response(MOCK_VALID_PAYLOAD)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            scenario="분수 덧셈 탐색",
            misconception="분모 통분 불가",
            framework=mock_framework,
        )

        assert status == "ok"
        assert len(payload["strengths"]) == 1
        assert len(payload["improvements"]) == 1
        assert len(payload["brief_feedback"]) == 2
        assert payload["version"] == 1

    @pytest.mark.asyncio
    async def test_bad_json_returns_failed(self, synthesizer, mock_framework):
        """Malformed JSON returns failed status."""
        mock_resp = Mock()
        mock_resp.output_text = "not valid json {{{"
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert status == "failed"
        assert FALLBACK_FEEDBACK in payload["brief_feedback"][0]

    @pytest.mark.asyncio
    async def test_hallucinated_message_id_dropped(
        self, synthesizer, mock_framework
    ):
        """Strengths with invalid message_id are dropped."""
        bad_payload = {
            "brief_feedback": ["좋은 피드백이에요."],
            "strengths": [
                {
                    "message_id": 999,
                    "quote": "존재하지 않는 메시지",
                    "reason": "테스트",
                }
            ],
            "improvements": [],
            "dialogue_coaching": [],
        }
        mock_resp = _make_mock_response(bad_payload)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert len(payload["strengths"]) == 0
        # degraded because brief_feedback exists but no detail
        assert status == "degraded"

    @pytest.mark.asyncio
    async def test_non_verbatim_quote_dropped(
        self, synthesizer, mock_framework
    ):
        """Strengths with non-verbatim quote are dropped."""
        bad_payload = {
            "brief_feedback": ["좋은 피드백이에요."],
            "strengths": [
                {
                    "message_id": 1,
                    "quote": "이건 실제 메시지에 없는 내용",
                    "reason": "테스트",
                }
            ],
            "improvements": [],
            "dialogue_coaching": [],
        }
        mock_resp = _make_mock_response(bad_payload)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert len(payload["strengths"]) == 0

    @pytest.mark.asyncio
    async def test_long_alt_question_dropped(self, synthesizer, mock_framework):
        """Improvements with alt_question > 60 chars dropped."""
        long_question = "가" * 61  # 61 Korean chars
        bad_payload = {
            "brief_feedback": ["좋은 피드백이에요."],
            "strengths": [],
            "improvements": [
                {
                    "student_message_id": 2,
                    "student_quote": "분자끼리 더했어요.",
                    "missed_reason": "테스트",
                    "alternative_question": long_question,
                    "alternative_reason": "테스트",
                }
            ],
            "dialogue_coaching": [],
        }
        mock_resp = _make_mock_response(bad_payload)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert len(payload["improvements"]) == 0

    @pytest.mark.asyncio
    async def test_tutor_annotation_dropped(self, synthesizer, mock_framework):
        """dialogue_coaching entries for tutor role are dropped."""
        payload_with_tutor = dict(MOCK_VALID_PAYLOAD)
        payload_with_tutor["dialogue_coaching"] = [
            {
                "message_id": 0,
                "role": "tutor",
                "marker": "good_moment",
                "note": "멘토 메시지",
            },
            {
                "message_id": 1,
                "role": "teacher",
                "marker": "good_moment",
                "note": "좋아요",
            },
        ]
        mock_resp = _make_mock_response(payload_with_tutor)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert len(payload["dialogue_coaching"]) == 1
        assert payload["dialogue_coaching"][0]["role"] == "teacher"

    @pytest.mark.asyncio
    async def test_long_brief_feedback_truncated(
        self, synthesizer, mock_framework
    ):
        """brief_feedback items > 70 chars are truncated."""
        long_item = "가" * 80
        payload_data = dict(MOCK_VALID_PAYLOAD)
        payload_data["brief_feedback"] = [long_item]
        mock_resp = _make_mock_response(payload_data)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert len(payload["brief_feedback"][0]) <= 71

    @pytest.mark.asyncio
    async def test_empty_brief_feedback_returns_failed(
        self, synthesizer, mock_framework
    ):
        """All empty brief_feedback results in failed status."""
        empty_payload = {
            "brief_feedback": [],
            "strengths": [],
            "improvements": [],
            "dialogue_coaching": [],
        }
        mock_resp = _make_mock_response(empty_payload)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert status == "failed"

    @pytest.mark.asyncio
    async def test_prompt_includes_question_analyses(
        self, synthesizer, mock_framework
    ):
        """Per-question classifications are included in the LLM prompt."""
        mock_resp = _make_mock_response(MOCK_VALID_PAYLOAD)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            question_analyses=[
                {
                    "message_id": 1,
                    "label": "Pressing",
                    "confidence": 0.87,
                    "reasoning": {"summary": "학생 사고를 탐색함"},
                }
            ],
            framework=mock_framework,
        )

        prompt = synthesizer.client.responses.create.call_args.kwargs["input"][
            0
        ]["content"]
        assert "Per-Question Analysis Results" in prompt
        assert "Message 1: Pressing" in prompt
        assert "학생 사고를 탐색함" in prompt

    @pytest.mark.asyncio
    async def test_non_dict_payload_returns_failed(
        self, synthesizer, mock_framework
    ):
        """A non-object JSON payload does not crash validation."""
        mock_resp = _make_mock_response(["not", "an", "object"])
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert status == "failed"
        assert FALLBACK_FEEDBACK in payload["brief_feedback"][0]

    @pytest.mark.asyncio
    async def test_non_dict_sections_are_dropped(
        self, synthesizer, mock_framework
    ):
        """Malformed section items are dropped instead of raising."""
        bad_payload = {
            "brief_feedback": ["좋은 피드백이에요."],
            "strengths": ["bad"],
            "improvements": ["bad"],
            "dialogue_coaching": ["bad"],
        }
        mock_resp = _make_mock_response(bad_payload)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert payload["strengths"] == []
        assert payload["improvements"] == []
        assert payload["dialogue_coaching"] == []
        assert status == "degraded"

    @pytest.mark.asyncio
    async def test_strength_must_reference_teacher_message(
        self, synthesizer, mock_framework
    ):
        """Strengths must point at teacher messages."""
        bad_payload = dict(MOCK_VALID_PAYLOAD)
        bad_payload["strengths"] = [
            {
                "message_id": 2,
                "quote": "분자끼리 더했어요.",
                "reason": "학생 메시지는 강점 대상이 아니에요.",
            }
        ]
        mock_resp = _make_mock_response(bad_payload)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert payload["strengths"] == []
        assert status == "degraded"

    @pytest.mark.asyncio
    async def test_improvement_must_reference_student_message_and_quote(
        self, synthesizer, mock_framework
    ):
        """Improvements must point at student messages with verbatim quote."""
        bad_payload = dict(MOCK_VALID_PAYLOAD)
        bad_payload["improvements"] = [
            {
                "student_message_id": 1,
                "student_quote": "어떻게 답을 구했어?",
                "missed_reason": "교사 메시지는 개선 대상이 아니에요.",
                "alternative_question": "왜 그렇게 생각했어?",
                "alternative_reason": "근거를 확인해요.",
            },
            {
                "student_message_id": 2,
                "student_quote": "없는 인용",
                "missed_reason": "인용이 원문에 없어요.",
                "alternative_question": "왜 그렇게 생각했어?",
                "alternative_reason": "근거를 확인해요.",
            },
        ]
        mock_resp = _make_mock_response(bad_payload)
        synthesizer.client.responses.create = AsyncMock(return_value=mock_resp)

        payload, status = await synthesizer.synthesize(
            messages=MOCK_MESSAGES,
            framework=mock_framework,
        )

        assert payload["improvements"] == []
        assert status == "degraded"


class TestPromptHash:
    """Tests for prompt_hash utility."""

    def test_hash_is_sha256_hex(self):
        """Hash is 64-char hex string."""
        h = prompt_hash("test content")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_deterministic(self):
        """Same input produces same hash."""
        h1 = prompt_hash("hello")
        h2 = prompt_hash("hello")
        assert h1 == h2

    def test_hash_differs_for_different_input(self):
        """Different input produces different hash."""
        h1 = prompt_hash("hello")
        h2 = prompt_hash("world")
        assert h1 != h2
