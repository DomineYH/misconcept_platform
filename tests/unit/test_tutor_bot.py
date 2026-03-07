"""Unit tests for TutorBot service (conversation pair analysis)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.dialogue_analysis import (
    SENSITIVITY_PRESETS,
    calculate_jaccard_similarity,
    check_low_leverage_patterns,
    check_vague_patterns,
    detect_repetitive_dialogue_simple,
    extract_recent_pairs,
)
from src.services.tutor_bot import TutorBot


class TestExtractRecentPairs:
    """Tests for extract_recent_pairs helper function."""

    def test_empty_exchanges(self):
        """Should return empty list for empty exchanges."""
        result = extract_recent_pairs([])
        assert result == []

    def test_single_exchange(self):
        """Should return empty list for single exchange."""
        exchanges = [{"role": "teacher", "content": "Hello"}]
        result = extract_recent_pairs(exchanges)
        assert result == []

    def test_one_complete_pair(self):
        """Should extract one teacher-student pair."""
        exchanges = [
            {"role": "teacher", "content": "What is 2+2?"},
            {"role": "student", "content": "I think it's 4."},
        ]
        result = extract_recent_pairs(exchanges)
        assert len(result) == 1
        assert result[0] == ("What is 2+2?", "I think it's 4.")

    def test_multiple_pairs(self):
        """Should extract multiple pairs in order."""
        exchanges = [
            {"role": "teacher", "content": "Q1"},
            {"role": "student", "content": "A1"},
            {"role": "teacher", "content": "Q2"},
            {"role": "student", "content": "A2"},
            {"role": "teacher", "content": "Q3"},
            {"role": "student", "content": "A3"},
        ]
        result = extract_recent_pairs(exchanges, max_pairs=3)
        assert len(result) == 3
        assert result[0] == ("Q1", "A1")
        assert result[1] == ("Q2", "A2")
        assert result[2] == ("Q3", "A3")

    def test_max_pairs_limit(self):
        """Should respect max_pairs limit."""
        exchanges = [
            {"role": "teacher", "content": "Q1"},
            {"role": "student", "content": "A1"},
            {"role": "teacher", "content": "Q2"},
            {"role": "student", "content": "A2"},
            {"role": "teacher", "content": "Q3"},
            {"role": "student", "content": "A3"},
        ]
        result = extract_recent_pairs(exchanges, max_pairs=2)
        assert len(result) == 2
        # Should get the most recent 2 pairs
        assert result[0] == ("Q2", "A2")
        assert result[1] == ("Q3", "A3")

    def test_handles_tutor_messages(self):
        """Should skip tutor messages when extracting pairs."""
        exchanges = [
            {"role": "teacher", "content": "Q1"},
            {"role": "student", "content": "A1"},
            {"role": "tutor", "content": "Feedback"},
            {"role": "teacher", "content": "Q2"},
            {"role": "student", "content": "A2"},
        ]
        result = extract_recent_pairs(exchanges, max_pairs=3)
        assert len(result) == 2
        assert result[0] == ("Q1", "A1")
        assert result[1] == ("Q2", "A2")

    def test_handles_consecutive_teacher_messages(self):
        """Should handle consecutive teacher messages."""
        exchanges = [
            {"role": "teacher", "content": "Q1"},
            {"role": "teacher", "content": "Q2"},  # Consecutive
            {"role": "student", "content": "A2"},
        ]
        result = extract_recent_pairs(exchanges)
        # Should only get Q2-A2 pair
        assert len(result) == 1
        assert result[0] == ("Q2", "A2")


class TestCalculateJaccardSimilarity:
    """Tests for calculate_jaccard_similarity helper function."""

    def test_identical_texts(self):
        """Identical texts should have similarity 1.0."""
        result = calculate_jaccard_similarity("hello world", "hello world")
        assert result == 1.0

    def test_completely_different_texts(self):
        """Completely different texts should have similarity 0.0."""
        result = calculate_jaccard_similarity("hello world", "foo bar")
        assert result == 0.0

    def test_partial_overlap(self):
        """Partial overlap should give intermediate similarity."""
        result = calculate_jaccard_similarity(
            "hello world foo", "hello world bar"
        )
        # Intersection: {hello, world} = 2
        # Union: {hello, world, foo, bar} = 4
        # Similarity: 2/4 = 0.5
        assert result == 0.5

    def test_empty_texts(self):
        """Empty texts should return 0.0."""
        assert calculate_jaccard_similarity("", "") == 0.0
        assert calculate_jaccard_similarity("hello", "") == 0.0
        assert calculate_jaccard_similarity("", "hello") == 0.0

    def test_case_insensitive(self):
        """Similarity should be case-insensitive."""
        result = calculate_jaccard_similarity("Hello World", "hello world")
        assert result == 1.0

    def test_punctuation_ignored(self):
        """Punctuation should be ignored."""
        result = calculate_jaccard_similarity("Hello, world!", "Hello world")
        assert result == 1.0

    def test_korean_text(self):
        """Should work with Korean text."""
        result = calculate_jaccard_similarity(
            "안녕하세요 반갑습니다", "안녕하세요 반갑습니다"
        )
        assert result == 1.0

    def test_mixed_language(self):
        """Should work with mixed language text."""
        result = calculate_jaccard_similarity(
            "Hello 안녕하세요", "Hello 안녕하세요 world"
        )
        # Intersection: {hello, 안녕하세요} = 2
        # Union: {hello, 안녕하세요, world} = 3
        assert result == pytest.approx(2 / 3, rel=0.01)


class TestDetectRepetitiveDialogueSimple:
    """Tests for detect_repetitive_dialogue_simple function."""

    def test_insufficient_pairs(self):
        """Should return False with less than 2 pairs."""
        assert detect_repetitive_dialogue_simple([]) is False
        assert detect_repetitive_dialogue_simple([("Q1", "A1")]) is False

    def test_no_repetition(self):
        """Should return False for non-repetitive dialogue."""
        pairs = [
            ("What is 2+2?", "I think 4."),
            ("Why do you think so?", "Because 2 and 2 make 4."),
            ("Can you explain more?", "Adding two numbers gives the sum."),
        ]
        result = detect_repetitive_dialogue_simple(pairs, threshold=0.7)
        assert result is False

    def test_teacher_repetition(self):
        """Should detect repetitive teacher questions."""
        pairs = [
            ("What do you think?", "I think it's correct."),
            ("What do you think about that?", "I'm not sure."),
        ]
        result = detect_repetitive_dialogue_simple(pairs, threshold=0.6)
        assert result is True

    def test_student_repetition(self):
        """Should detect repetitive student responses."""
        pairs = [
            ("What is the answer?", "I don't know."),
            ("Can you try again?", "I don't know."),
        ]
        result = detect_repetitive_dialogue_simple(pairs, threshold=0.7)
        assert result is True

    def test_threshold_sensitivity(self):
        """Higher threshold should require more similarity."""
        pairs = [
            ("What do you think?", "Answer one"),
            ("What do you think about it?", "Answer two"),
        ]
        # Lower threshold should detect
        assert detect_repetitive_dialogue_simple(pairs, threshold=0.5) is True
        # Higher threshold might not detect
        assert detect_repetitive_dialogue_simple(pairs, threshold=0.9) is False


class TestSensitivityPresets:
    """Tests for SENSITIVITY_PRESETS configuration."""

    def test_presets_contain_all_levels(self):
        """Should have high, medium, low presets."""
        assert "high" in SENSITIVITY_PRESETS
        assert "medium" in SENSITIVITY_PRESETS
        assert "low" in SENSITIVITY_PRESETS

    def test_preset_keys(self):
        """Each preset should have all required keys."""
        required = {
            "similarity_threshold",
            "vague_min_matches",
            "low_leverage_count",
            "use_llm",
        }
        for level, preset in SENSITIVITY_PRESETS.items():
            assert (
                set(preset.keys()) == required
            ), f"{level} preset missing keys"

    def test_high_is_most_sensitive(self):
        """HIGH should have lowest thresholds."""
        h = SENSITIVITY_PRESETS["high"]
        m = SENSITIVITY_PRESETS["medium"]
        assert h["similarity_threshold"] < m["similarity_threshold"]
        assert h["low_leverage_count"] <= m["low_leverage_count"]

    def test_low_is_least_sensitive(self):
        """LOW should have highest thresholds."""
        m = SENSITIVITY_PRESETS["medium"]
        lo = SENSITIVITY_PRESETS["low"]
        assert lo["similarity_threshold"] > m["similarity_threshold"]
        assert lo["low_leverage_count"] >= m["low_leverage_count"]

    def test_low_disables_llm(self):
        """LOW should disable LLM analysis."""
        assert SENSITIVITY_PRESETS["low"]["use_llm"] is False
        assert SENSITIVITY_PRESETS["high"]["use_llm"] is True


class TestCheckPatterns:
    """Tests for pattern checking functions."""

    def test_low_leverage_short_question(self):
        """Should detect short questions as low-leverage."""
        assert check_low_leverage_patterns("Is it?") is True
        assert check_low_leverage_patterns("Why?") is True

    def test_low_leverage_yes_no_question(self):
        """Should detect yes/no questions as low-leverage."""
        assert check_low_leverage_patterns("Is it correct?") is True
        assert check_low_leverage_patterns("Do you understand?") is True

    def test_low_leverage_directive(self):
        """Should detect directive statements as low-leverage."""
        assert check_low_leverage_patterns("You should try adding them") is True
        assert check_low_leverage_patterns("Try this approach instead") is True

    def test_high_leverage_question(self):
        """Should not flag high-leverage questions."""
        assert (
            check_low_leverage_patterns(
                "Can you explain your reasoning for that answer?"
            )
            is False
        )
        assert (
            check_low_leverage_patterns(
                "How does this connect to what we learned before?"
            )
            is False
        )

    def test_low_leverage_with_min_count(self):
        """Should respect min_count for consecutive detection."""
        questions = ["Is it?", "Do you get it?", "Why?"]
        # min_count=1: single occurrence triggers
        assert (
            check_low_leverage_patterns(
                "Is it?", recent_questions=questions, min_count=1
            )
            is True
        )
        # min_count=3: need 3 consecutive low-leverage
        assert (
            check_low_leverage_patterns(
                "Is it?", recent_questions=questions, min_count=3
            )
            is True
        )
        # min_count=5: not enough (3 recent + 1 current = 4)
        assert (
            check_low_leverage_patterns(
                "Is it?", recent_questions=questions, min_count=5
            )
            is False
        )

    def test_low_leverage_min_count_default(self):
        """Default min_count=1 should match current behavior."""
        assert check_low_leverage_patterns("Is it?") is True

    def test_vague_patterns_insufficient_questions(self):
        """Should return False with less than 3 questions."""
        assert check_vague_patterns(["Q1", "Q2"]) is False

    def test_vague_patterns_detected(self):
        """Should detect vague question patterns."""
        questions = [
            "What do you think?",
            "Any thoughts on this?",
            "What else can you add?",
        ]
        assert check_vague_patterns(questions) is True

    def test_vague_patterns_not_detected(self):
        """Should not flag non-vague questions."""
        questions = [
            "What is 2+2?",
            "Why did you choose that method?",
            "Can you show your work?",
        ]
        assert check_vague_patterns(questions) is False

    def test_vague_patterns_min_matches(self):
        """Should respect min_matches parameter."""
        questions = [
            "What do you think?",
            "Any thoughts on this?",
            "What is 2+2?",
        ]
        # min_matches=1: only 1 vague needed → True (2 found)
        assert check_vague_patterns(questions, min_matches=1) is True
        # min_matches=2: need 2 vague → True (2 found)
        assert check_vague_patterns(questions, min_matches=2) is True
        # min_matches=3: need 3 vague → False (only 2)
        assert check_vague_patterns(questions, min_matches=3) is False


class TestTutorBotAnalyzeConversation:
    """Tests for TutorBot.analyze_conversation method."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, mock_db_session):
        """Should respect intervention rate limiting."""
        bot = TutorBot(mock_db_session, template_id=1, intervention_threshold=1)
        bot.intervention_count = 1  # Already at threshold

        exchanges = [
            {"role": "teacher", "content": "Q1"},
            {"role": "student", "content": "A1"},
        ]

        result, reason = await bot.analyze_conversation(
            exchanges, "Is it correct?", "Yes"
        )
        assert result is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_single_pair_low_leverage_medium(self, mock_db_session):
        """Medium sensitivity: single low-leverage should NOT trigger."""
        bot = TutorBot(mock_db_session, template_id=1)

        result, reason = await bot.analyze_conversation([], "Is it?", "Yes")
        # Medium needs 2+ low-leverage, only 1 here
        assert result is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_repeated_low_leverage_medium(self, mock_db_session):
        """Medium sensitivity: 2 low-leverage questions should trigger."""
        bot = TutorBot(mock_db_session, template_id=1)

        exchanges = [
            {"role": "teacher", "content": "Is it?"},
            {"role": "student", "content": "Yes"},
        ]
        result, reason = await bot.analyze_conversation(
            exchanges, "Do you understand?", "No"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_repetitive_dialogue_detection(self, mock_db_session):
        """Should detect repetitive dialogue patterns."""
        bot = TutorBot(mock_db_session, template_id=1)

        # Create repetitive exchanges
        exchanges = [
            {"role": "teacher", "content": "What do you think?"},
            {"role": "student", "content": "I don't know."},
        ]

        # Mock the LLM call
        with patch.object(
            bot, "analyze_conversation_with_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = {
                "is_repetitive": False,
                "is_inappropriate": False,
                "reason": "",
            }

            # Current exchange is similar to previous
            result, reason = await bot.analyze_conversation(
                exchanges,
                "What do you think?",  # Same question
                "I don't know.",  # Same answer
            )
            # Should be detected by Jaccard similarity first
            assert result is True

    @pytest.mark.asyncio
    async def test_llm_analysis_called(self, mock_db_session):
        """Should call LLM analysis when Jaccard doesn't detect."""
        bot = TutorBot(mock_db_session, template_id=1)

        exchanges = [
            {"role": "teacher", "content": "What is 2+2?"},
            {"role": "student", "content": "I think 4."},
        ]

        with patch.object(
            bot, "analyze_conversation_with_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = {
                "is_repetitive": True,
                "is_inappropriate": False,
                "reason": "Similar semantic content",
            }

            result, reason = await bot.analyze_conversation(
                exchanges,
                "Why do you think so?",
                "Because math.",
            )
            # LLM should be called
            mock_llm.assert_called_once()
            assert result is True
            assert "Similar semantic content" in reason

    @pytest.mark.asyncio
    async def test_sensitivity_high_triggers_on_first_low_leverage(
        self, mock_db_session
    ):
        """HIGH sensitivity: single low-leverage triggers."""
        bot = TutorBot(mock_db_session, template_id=1, sensitivity="high")
        result, reason = await bot.analyze_conversation([], "Is it?", "Yes")
        assert result is True
        assert reason == "low_leverage"

    @pytest.mark.asyncio
    async def test_sensitivity_invalid_falls_back_to_medium(
        self, mock_db_session
    ):
        """Invalid sensitivity value should fall back to medium."""
        bot = TutorBot(mock_db_session, template_id=1, sensitivity="invalid")
        assert bot.sensitivity_config == SENSITIVITY_PRESETS["medium"]

    @pytest.mark.asyncio
    async def test_sensitivity_low_skips_llm(self, mock_db_session):
        """LOW sensitivity: LLM analysis should not be called."""
        bot = TutorBot(mock_db_session, template_id=1, sensitivity="low")
        exchanges = [
            {"role": "teacher", "content": "What is 2+2?"},
            {"role": "student", "content": "I think 4."},
        ]
        with patch.object(
            bot, "analyze_conversation_with_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = {
                "is_repetitive": False,
                "is_inappropriate": False,
                "reason": "",
            }
            await bot.analyze_conversation(exchanges, "Why?", "Because.")
            # LLM should NOT be called for low sensitivity
            mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_sensitivity_uses_preset_similarity_threshold(
        self, mock_db_session
    ):
        """Should use sensitivity-specific similarity threshold."""
        # HIGH sensitivity has lower threshold (0.5)
        bot_high = TutorBot(mock_db_session, template_id=1, sensitivity="high")
        assert (
            bot_high.sensitivity_config["similarity_threshold"]
            == SENSITIVITY_PRESETS["high"]["similarity_threshold"]
        )

        # LOW sensitivity has higher threshold (0.8)
        bot_low = TutorBot(mock_db_session, template_id=1, sensitivity="low")
        assert (
            bot_low.sensitivity_config["similarity_threshold"]
            == SENSITIVITY_PRESETS["low"]["similarity_threshold"]
        )

    @pytest.mark.asyncio
    async def test_sensitivity_default_is_medium(self, mock_db_session):
        """Default sensitivity should be medium."""
        bot = TutorBot(mock_db_session, template_id=1)
        assert bot.sensitivity_config == SENSITIVITY_PRESETS["medium"]


class TestTutorBotAnalyzeConversationWithLLM:
    """Tests for TutorBot.analyze_conversation_with_llm method."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_insufficient_pairs(self, mock_db_session):
        """Should return no issues for insufficient pairs."""
        bot = TutorBot(mock_db_session, template_id=1)
        result = await bot.analyze_conversation_with_llm([("Q1", "A1")])
        assert result["is_repetitive"] is False
        assert result["is_inappropriate"] is False

    @pytest.mark.asyncio
    async def test_llm_response_parsing(self, mock_db_session):
        """Should parse LLM JSON response correctly."""
        bot = TutorBot(mock_db_session, template_id=1)

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.output = [
            MagicMock(
                type="message",
                content=[
                    MagicMock(
                        type="output_text",
                        text=(
                            '{"is_repetitive": true,'
                            ' "is_inappropriate": false,'
                            ' "reason": "Test reason"}'
                        ),
                    )
                ],
            )
        ]

        with patch.object(
            bot.client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            pairs = [("Q1", "A1"), ("Q2", "A2")]
            result = await bot.analyze_conversation_with_llm(pairs)

            assert result["is_repetitive"] is True
            assert result["is_inappropriate"] is False
            assert result["reason"] == "Test reason"

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self, mock_db_session):
        """Should fall back to Jaccard on LLM error."""
        bot = TutorBot(mock_db_session, template_id=1)

        with patch.object(
            bot.client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            # Simulate API error
            from openai import APIError

            mock_create.side_effect = APIError(
                message="API Error", request=MagicMock(), body=None
            )

            # Repetitive pairs
            pairs = [
                ("What do you think?", "I don't know."),
                ("What do you think?", "I don't know."),
            ]
            result = await bot.analyze_conversation_with_llm(pairs)

            # Should use Jaccard fallback
            assert result["is_repetitive"] is True
