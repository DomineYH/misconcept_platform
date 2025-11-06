"""StudentBot service for role-playing student with misconception."""
import logging
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import config
from src.utils.cache import load_prompt_template

logger = logging.getLogger(__name__)


class StudentBot:
    """Chatbot simulating student with specific misconception."""

    def __init__(self, scenario_prompt: str, scenario_title: str,
                 student_profile: str = "Grade 5 student"):
        """Initialize StudentBot with scenario context.

        Args:
            scenario_prompt: System prompt defining misconception
            scenario_title: Scenario display name
            student_profile: Student characteristics
        """
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.CHAT_MODEL
        self.temperature = 0.7

        # Load cached system prompt template (T111 optimization)
        template = load_prompt_template("student_system.txt")

        # Format system prompt with scenario context
        self.system_prompt = template.format(
            scenario_title=scenario_title,
            student_profile=student_profile,
            prompt=scenario_prompt,
        )

    @retry(
        retry=retry_if_exception_type(
            (APIConnectionError, APIError, RateLimitError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_response(
        self, teacher_message: str, conversation_history: list[dict]
    ) -> str:
        """Generate student response to teacher question.

        Args:
            teacher_message: Latest teacher question
            conversation_history: Previous messages [{"role": str, "content":
                str}]

        Returns:
            Student response as string

        Raises:
            APIError: If OpenAI API fails after retries
        """
        try:
            # Build messages for API
            messages = [{"role": "system", "content": self.system_prompt}]

            # Add conversation history
            for msg in conversation_history:
                if msg["role"] == "teacher":
                    messages.append(
                        {"role": "user", "content": msg["content"]}
                    )
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
                max_tokens=150,  # Keep student responses concise
            )

            return response.choices[0].message.content.strip()

        except (APIConnectionError, RateLimitError, APIError) as e:
            logger.error(
                f"StudentBot API error: {type(e).__name__}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error in StudentBot: {str(e)}")
            raise APIError(f"Student response generation failed: {str(e)}")
