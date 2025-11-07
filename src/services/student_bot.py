"""StudentBot service for role-playing student with misconception."""

import logging
from typing import Optional

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import config
from src.services.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class StudentBot:
    """Chatbot simulating student with specific misconception."""

    def __init__(
        self,
        scenario_prompt: str,
        scenario_title: str,
        student_profile: str,
        db_session: AsyncSession,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """Initialize StudentBot with scenario context and optional config.

        Args:
            scenario_prompt: System prompt defining misconception
            scenario_title: Scenario display name
            student_profile: Student characteristics
            db_session: Database session for dynamic prompt loading
            model: Override default model (from config or DB)
            temperature: Override default temperature (0.0-2.0)
            max_tokens: Override default max tokens (50-500)
        """
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.db_session = db_session
        self.model = model or config.CHAT_MODEL
        self.temperature = temperature if temperature is not None else 0.7
        self.max_tokens = max_tokens or 150

        # Store scenario context for dynamic prompt formatting
        self.scenario_prompt = scenario_prompt
        self.scenario_title = scenario_title
        self.student_profile = student_profile

    @retry(
        retry=retry_if_exception_type(
            (APIConnectionError, APIError, RateLimitError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
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
            template = await PromptManager.get_active_prompt(
                self.db_session, "student"
            )

            # Format with scenario context
            system_prompt = template.format(
                scenario_title=self.scenario_title,
                student_profile=self.student_profile,
                prompt=self.scenario_prompt,
            )

            # Build messages for API
            messages = [{"role": "system", "content": system_prompt}]

            # Add conversation history
            for msg in conversation_history:
                if msg["role"] == "teacher":
                    messages.append({"role": "user", "content": msg["content"]})
                elif msg["role"] == "student":
                    messages.append(
                        {"role": "assistant", "content": msg["content"]}
                    )

            # Add current teacher message
            messages.append({"role": "user", "content": teacher_message})

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # Extract content
            content = response.choices[0].message.content.strip()

            # Extract usage information if available
            usage_dict = None
            if hasattr(response, "usage") and response.usage is not None:
                usage_dict = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return content, usage_dict

        except (APIConnectionError, RateLimitError, APIError) as e:
            logger.error(f"StudentBot API error: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in StudentBot: {str(e)}")
            raise APIError(f"Student response generation failed: {str(e)}")
