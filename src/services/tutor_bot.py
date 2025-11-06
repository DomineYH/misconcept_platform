"""TutorBot service for pedagogical feedback and intervention."""
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


class TutorBot:
    """Chatbot providing real-time pedagogical feedback."""

    def __init__(self):
        """Initialize TutorBot with system prompt."""
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.ANALYSIS_MODEL  # Can use faster model
        self.temperature = 0.3  # More consistent feedback

        # Load cached tutor system prompt (T111 optimization)
        self.system_prompt = load_prompt_template("tutor_system.txt")

        # Track interventions for rate limiting
        self.intervention_count = 0
        self.question_count = 0

    def should_intervene(
        self, recent_teacher_questions: list[str]
    ) -> bool:
        """Determine if tutor should provide feedback.

        Args:
            recent_teacher_questions: Last N teacher questions

        Returns:
            True if intervention needed, False otherwise
        """
        self.question_count += 1

        # Rate limiting: Max 3 interventions per 10 questions
        if self.question_count > 10:
            self.intervention_count = 0
            self.question_count = 0

        if self.intervention_count >= 3:
            return False

        # Heuristic checks for intervention triggers
        if len(recent_teacher_questions) < 2:
            return False

        latest = recent_teacher_questions[-1].lower()

        # Check for low-leverage patterns
        low_leverage_indicators = [
            latest.endswith("?") and len(latest.split()) < 5,  # Too short
            any(
                phrase in latest
                for phrase in ["yes or no", "is it", "are you", "do you"]
            ),
            "you should" in latest or "try this" in latest,  # Directive
        ]

        # Check for stagnation (similar questions)
        if len(recent_teacher_questions) >= 3:
            recent_3 = recent_teacher_questions[-3:]
            vague_questions = [
                q
                for q in recent_3
                if any(
                    phrase in q.lower()
                    for phrase in [
                        "what do you think",
                        "any thoughts",
                        "what else",
                    ]
                )
            ]
            if len(vague_questions) >= 2:
                return True

        # Intervene if low-leverage detected
        return any(low_leverage_indicators)

    @retry(
        retry=retry_if_exception_type(
            (APIConnectionError, APIError, RateLimitError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_feedback(
        self,
        teacher_question: str,
        student_response: str,
        recent_exchanges: list[dict],
    ) -> str | None:
        """Generate pedagogical feedback for teacher.

        Args:
            teacher_question: Latest teacher question
            student_response: Student's response
            recent_exchanges: Recent conversation context

        Returns:
            Feedback string if intervention triggered, None otherwise

        Raises:
            APIError: If OpenAI API fails after retries
        """
        # Extract recent teacher questions
        teacher_questions = [
            ex["content"]
            for ex in recent_exchanges[-5:]
            if ex["role"] == "teacher"
        ]
        teacher_questions.append(teacher_question)

        # Check if intervention needed
        if not self.should_intervene(teacher_questions):
            return None

        try:
            # Build analysis context
            context = "Recent conversation:\n"
            for ex in recent_exchanges[-4:]:
                context += f"{ex['role'].upper()}: {ex['content']}\n"
            context += f"TEACHER: {teacher_question}\n"
            context += f"STUDENT: {student_response}\n"

            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": f"{context}\nProvide brief, constructive feedback for the teacher.",
                },
            ]

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=100,
            )

            self.intervention_count += 1
            return response.choices[0].message.content.strip()

        except (APIConnectionError, RateLimitError, APIError) as e:
            logger.error(
                f"TutorBot API error: {type(e).__name__}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error in TutorBot: {str(e)}")
            raise APIError(f"Tutor feedback generation failed: {str(e)}")
