"""StudentBot service for role-playing student with misconception."""

import logging
from typing import Optional

from openai import APIConnectionError, APIError, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import config
from src.services.base import OpenAIBaseService, openai_retry
from src.services.prompt_manager import PromptManager
from src.utils.openai_helpers import extract_response_text

logger = logging.getLogger(__name__)


class StudentBot(OpenAIBaseService):
    """Chatbot simulating student with specific misconception."""

    def __init__(
        self,
        scenario_prompt: str,
        scenario_title: str,
        student_profile: str,
        db_session: AsyncSession,
        template_id: int,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ):
        """Initialize StudentBot with scenario context and optional config.

        Args:
            scenario_prompt: System prompt defining misconception
            scenario_title: Scenario display name
            student_profile: Student characteristics
            db_session: Database session for dynamic prompt loading
            template_id: Prompt template ID for this scenario
            model: Override default model (from config or DB)
            reasoning_effort: Override reasoning effort (minimal, low,
                medium, high)
            max_tokens: Override default max tokens (50-500)
        """
        super().__init__()
        self.db_session = db_session
        self.template_id = template_id
        self.model = model or config.CHAT_MODEL
        self.reasoning_effort = reasoning_effort or config.STUDENT_REASONING
        self.max_tokens = max_tokens or config.STUDENT_MAX_TOKENS

        # Store scenario context for dynamic prompt formatting
        self.scenario_prompt = scenario_prompt
        self.scenario_title = scenario_title
        self.student_profile = student_profile

    @openai_retry
    async def generate_response(
        self, teacher_message: str, conversation_history: list[dict]
    ) -> tuple[str, Optional[dict]]:
        """Generate student response to teacher question.

        Args:
            teacher_message: Latest teacher question
            conversation_history: Previous messages [{"role": str, "content":
                str}]

        Returns:
            Tuple of (student_response, usage_dict or None)
            usage_dict contains: prompt_tokens, completion_tokens,
            total_tokens

        Raises:
            APIError: If OpenAI API fails after retries
        """
        try:
            # Load dynamic prompt template (5-min cache, <10ms)
            template = await PromptManager.get_template_text_by_id(
                self.db_session, self.template_id
            )

            # Format with scenario context
            system_prompt = template.format(
                scenario_title=self.scenario_title,
                student_profile=self.student_profile,
                prompt=self.scenario_prompt,
            )

            # Build input for Responses API (developer role)
            input_messages = [{"role": "developer", "content": system_prompt}]

            # Add conversation history
            for msg in conversation_history:
                if msg["role"] == "teacher":
                    input_messages.append(
                        {"role": "user", "content": msg["content"]}
                    )
                elif msg["role"] == "student":
                    input_messages.append(
                        {"role": "assistant", "content": msg["content"]}
                    )

            # Add current teacher message
            input_messages.append({"role": "user", "content": teacher_message})

            # OpenAI Responses API 호출 (GPT-5 with reasoning)
            response = await self.client.responses.create(
                model=self.model,
                input=input_messages,
                max_output_tokens=self.max_tokens,
                reasoning={"effort": self.reasoning_effort},
            )

            # Extract content (Responses API output 처리)
            content = extract_response_text(response)

            # Extract usage information if available
            usage_dict = None
            if hasattr(response, "usage") and response.usage is not None:
                usage_dict = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return content, usage_dict

        except (APIConnectionError, RateLimitError, APIError) as e:
            logger.error(f"StudentBot API error: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in StudentBot: {str(e)}")
            raise RuntimeError(
                f"Student response generation failed: {str(e)}"
            ) from e
