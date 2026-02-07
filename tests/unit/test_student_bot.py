"""Unit tests for StudentBot service.

Tests student response generation with mocked OpenAI Responses API.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from openai import APIConnectionError, APIError, RateLimitError
from tenacity import RetryError

from src.services.student_bot import StudentBot


def _make_responses_api_mock(
    output_text: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
    total_tokens: int = 150,
) -> Mock:
    """Create mock matching OpenAI Responses API structure.

    Args:
        output_text: Text content to return
        input_tokens: Mock input token count
        output_tokens: Mock output token count
        total_tokens: Mock total token count

    Returns:
        Mock object with output_text and usage attributes
    """
    mock_response = Mock()
    mock_response.output_text = output_text
    mock_response.usage = Mock(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
    return mock_response


class TestStudentBotInit:
    """Tests for StudentBot initialization."""

    def test_init_with_defaults(self):
        """Should use config defaults when no overrides given."""
        with patch("src.services.base.AsyncOpenAI"):
            bot = StudentBot(
                scenario_prompt="Test prompt",
                scenario_title="Test Title",
                student_profile="Grade 5",
                db_session=Mock(),
                template_id=1,
            )

        assert bot.scenario_prompt == "Test prompt"
        assert bot.scenario_title == "Test Title"
        assert bot.student_profile == "Grade 5"
        assert bot.template_id == 1

    def test_init_with_overrides(self):
        """Should use provided overrides over config defaults."""
        with patch("src.services.base.AsyncOpenAI"):
            bot = StudentBot(
                scenario_prompt="Test prompt",
                scenario_title="Test Title",
                student_profile="Grade 5",
                db_session=Mock(),
                template_id=1,
                model="gpt-4-turbo",
                reasoning_effort="high",
                max_tokens=500,
            )

        assert bot.model == "gpt-4-turbo"
        assert bot.reasoning_effort == "high"
        assert bot.max_tokens == 500


class TestStudentBotGenerateResponse:
    """Tests for StudentBot.generate_response method."""

    @pytest.fixture
    def bot(self):
        """Create StudentBot with mocked OpenAI client."""
        with patch("src.services.base.AsyncOpenAI") as mock_cls:
            bot = StudentBot(
                scenario_prompt="Moon misconception",
                scenario_title="Moon Phases",
                student_profile="Grade 5 student",
                db_session=AsyncMock(),
                template_id=1,
                model="gpt-5",
            )
            bot.client = mock_cls.return_value
            return bot

    async def test_returns_content_and_usage(self, bot):
        """Should return response text and usage dict."""
        mock_response = _make_responses_api_mock(
            "The moon makes its own light!",
            input_tokens=200,
            output_tokens=30,
            total_tokens=230,
        )
        bot.client.responses.create = AsyncMock(
            return_value=mock_response
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value=(
                "You are a student. Title: {scenario_title}. "
                "Profile: {student_profile}. Prompt: {prompt}"
            ),
        ):
            content, usage = await bot.generate_response(
                "Why does the moon shine?", []
            )

        assert content == "The moon makes its own light!"
        assert usage == {
            "prompt_tokens": 200,
            "completion_tokens": 30,
            "total_tokens": 230,
        }

    async def test_returns_none_usage_when_missing(self, bot):
        """Should return None usage when response has no usage."""
        mock_response = Mock()
        mock_response.output_text = "Student answer"
        mock_response.usage = None

        bot.client.responses.create = AsyncMock(
            return_value=mock_response
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            content, usage = await bot.generate_response(
                "Question?", []
            )

        assert content == "Student answer"
        assert usage is None

    async def test_system_prompt_construction(self, bot):
        """Should format template with scenario context."""
        mock_response = _make_responses_api_mock("Response")
        create_mock = AsyncMock(return_value=mock_response)
        bot.client.responses.create = create_mock

        template = (
            "Title: {scenario_title}. "
            "Profile: {student_profile}. "
            "Misconception: {prompt}"
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value=template,
        ):
            await bot.generate_response("Hello", [])

        # Verify API call
        create_mock.assert_called_once()
        call_kwargs = create_mock.call_args.kwargs
        input_msgs = call_kwargs["input"]

        # Developer message should contain formatted template
        developer_msg = input_msgs[0]
        assert developer_msg["role"] == "developer"
        assert "Moon Phases" in developer_msg["content"]
        assert "Grade 5 student" in developer_msg["content"]
        assert "Moon misconception" in developer_msg["content"]

    async def test_conversation_history_building(self, bot):
        """Should map teacher/student roles to user/assistant."""
        mock_response = _make_responses_api_mock("Response")
        create_mock = AsyncMock(return_value=mock_response)
        bot.client.responses.create = create_mock

        history = [
            {"role": "teacher", "content": "What is the moon?"},
            {"role": "student", "content": "A big rock."},
            {"role": "teacher", "content": "Does it shine?"},
            {"role": "student", "content": "Yes, by itself."},
        ]

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="System {scenario_title} {student_profile} {prompt}",
        ):
            await bot.generate_response(
                "Why do you think so?", history
            )

        call_kwargs = create_mock.call_args.kwargs
        input_msgs = call_kwargs["input"]

        # Structure: developer + 4 history + 1 current
        assert len(input_msgs) == 6
        assert input_msgs[0]["role"] == "developer"
        assert input_msgs[1] == {
            "role": "user",
            "content": "What is the moon?",
        }
        assert input_msgs[2] == {
            "role": "assistant",
            "content": "A big rock.",
        }
        assert input_msgs[3] == {
            "role": "user",
            "content": "Does it shine?",
        }
        assert input_msgs[4] == {
            "role": "assistant",
            "content": "Yes, by itself.",
        }
        assert input_msgs[5] == {
            "role": "user",
            "content": "Why do you think so?",
        }

    async def test_api_call_parameters(self, bot):
        """Should pass correct parameters to Responses API."""
        mock_response = _make_responses_api_mock("Response")
        create_mock = AsyncMock(return_value=mock_response)
        bot.client.responses.create = create_mock

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            await bot.generate_response("Hello", [])

        call_kwargs = create_mock.call_args.kwargs
        assert call_kwargs["model"] == "gpt-5"
        assert call_kwargs["max_output_tokens"] == bot.max_tokens
        assert call_kwargs["reasoning"] == {
            "effort": bot.reasoning_effort
        }

    async def test_template_loading_via_prompt_manager(self, bot):
        """Should call PromptManager with correct template_id."""
        mock_response = _make_responses_api_mock("Response")
        bot.client.responses.create = AsyncMock(
            return_value=mock_response
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ) as mock_get:
            await bot.generate_response("Hello", [])

        mock_get.assert_called_once_with(bot.db_session, 1)

    async def test_api_error_retries_then_raises(self, bot):
        """Should retry on APIError then raise RetryError."""
        bot.client.responses.create = AsyncMock(
            side_effect=APIError(
                message="Server error",
                request=Mock(),
                body=None,
            )
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            with pytest.raises(RetryError):
                await bot.generate_response("Hello", [])

        # Should have been called 3 times (tenacity retries)
        assert bot.client.responses.create.call_count == 3

    async def test_rate_limit_error_retries_then_raises(self, bot):
        """Should retry on RateLimitError then raise RetryError."""
        bot.client.responses.create = AsyncMock(
            side_effect=RateLimitError(
                message="Rate limited",
                response=Mock(status_code=429, headers={}),
                body=None,
            )
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            with pytest.raises(RetryError):
                await bot.generate_response("Hello", [])

        assert bot.client.responses.create.call_count == 3

    async def test_unexpected_error_wraps_in_runtime_error(self, bot):
        """Should wrap unexpected errors in RuntimeError."""
        bot.client.responses.create = AsyncMock(
            side_effect=ValueError("Unexpected")
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            with pytest.raises(
                RuntimeError, match="Student response generation failed"
            ):
                await bot.generate_response("Hello", [])

    async def test_empty_response_raises_value_error(self, bot):
        """Should raise ValueError for empty response content."""
        mock_response = Mock()
        mock_response.output_text = ""
        mock_response.output = None
        # Remove model_dump to prevent fallback path
        if hasattr(mock_response, "model_dump"):
            del mock_response.model_dump

        bot.client.responses.create = AsyncMock(
            return_value=mock_response
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            with pytest.raises(RuntimeError):
                await bot.generate_response("Hello", [])

    async def test_empty_conversation_history(self, bot):
        """Should work with empty conversation history."""
        mock_response = _make_responses_api_mock("First response")
        create_mock = AsyncMock(return_value=mock_response)
        bot.client.responses.create = create_mock

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            content, usage = await bot.generate_response(
                "Hello, student!", []
            )

        assert content == "First response"

        # Only developer + current message
        call_kwargs = create_mock.call_args.kwargs
        input_msgs = call_kwargs["input"]
        assert len(input_msgs) == 2
        assert input_msgs[0]["role"] == "developer"
        assert input_msgs[1]["role"] == "user"

    async def test_usage_dict_extraction(self, bot):
        """Should extract all usage fields correctly."""
        mock_response = _make_responses_api_mock(
            "Response",
            input_tokens=500,
            output_tokens=200,
            total_tokens=700,
        )
        bot.client.responses.create = AsyncMock(
            return_value=mock_response
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            _, usage = await bot.generate_response("Hello", [])

        assert usage["prompt_tokens"] == 500
        assert usage["completion_tokens"] == 200
        assert usage["total_tokens"] == 700

    async def test_response_without_usage_attr(self, bot):
        """Should return None usage when no usage attribute."""
        mock_response = Mock(spec=[])
        mock_response.output_text = "Response text"

        bot.client.responses.create = AsyncMock(
            return_value=mock_response
        )

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            _, usage = await bot.generate_response("Hello", [])

        assert usage is None

    async def test_ignores_non_teacher_student_history(self, bot):
        """Should skip tutor messages in conversation history."""
        mock_response = _make_responses_api_mock("Response")
        create_mock = AsyncMock(return_value=mock_response)
        bot.client.responses.create = create_mock

        history = [
            {"role": "teacher", "content": "Question?"},
            {"role": "student", "content": "Answer."},
            {"role": "tutor", "content": "Feedback."},
        ]

        with patch(
            "src.services.student_bot.PromptManager"
            ".get_template_text_by_id",
            new_callable=AsyncMock,
            return_value="Template {scenario_title} {student_profile} {prompt}",
        ):
            await bot.generate_response("Follow up?", history)

        call_kwargs = create_mock.call_args.kwargs
        input_msgs = call_kwargs["input"]
        # developer + teacher(user) + student(assistant) + current
        # tutor messages are skipped
        assert len(input_msgs) == 4
        roles = [m["role"] for m in input_msgs]
        assert roles == ["developer", "user", "assistant", "user"]
