"""TutorBot service for pedagogical feedback and intervention."""

import logging
from typing import Optional

from openai import APIConnectionError, APIError, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import config
from src.services.base import OpenAIBaseService, openai_retry
from src.services.prompt_manager import PromptManager
from src.utils.openai_helpers import extract_response_text

logger = logging.getLogger(__name__)


class TutorBot(OpenAIBaseService):
    """Chatbot providing real-time pedagogical feedback."""

    def __init__(
        self,
        db_session: AsyncSession,
        scenario_title: str = "",
        prompt: str = "",
        student_profile: str = "",
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        max_tokens: Optional[int] = None,
        intervention_threshold: Optional[int] = None,
    ):
        """Initialize TutorBot with scenario context and optional config.

        Args:
            db_session: Database session for dynamic prompt loading
            scenario_title: Scenario display name
            prompt: System prompt defining misconception
            student_profile: Student characteristics
            model: Override default model (from config or DB)
            reasoning_effort: Override reasoning effort (minimal, low,
                medium, high)
            max_tokens: Override default max tokens (50-300)
            intervention_threshold: Interventions per 10 questions (1-10)
        """
        super().__init__()
        self.db_session = db_session
        self.model = model or config.ANALYSIS_MODEL
        self.reasoning_effort = reasoning_effort or config.TUTOR_REASONING
        self.max_tokens = max_tokens or config.TUTOR_MAX_TOKENS
        self.intervention_threshold = (
            intervention_threshold or config.TUTOR_INTERVENTION_THRESHOLD
        )

        # Store scenario context for dynamic prompt formatting
        self.scenario_title = scenario_title
        self.prompt = prompt
        self.student_profile = student_profile

        # Track interventions for rate limiting
        self.intervention_count = 0
        self.question_count = 0

    def should_intervene(self, recent_teacher_questions: list[str]) -> bool:
        """Determine if tutor should provide feedback.

        Args:
            recent_teacher_questions: Last N teacher questions

        Returns:
            True if intervention needed, False otherwise
        """
        self.question_count += 1

        # Rate limiting: Max N interventions per 10 questions
        if self.question_count > 10:
            self.intervention_count = 0
            self.question_count = 0

        if self.intervention_count >= self.intervention_threshold:
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

    @openai_retry
    async def generate_feedback(
        self,
        teacher_question: str,
        student_response: str,
        recent_exchanges: list[dict],
    ) -> tuple[str | None, Optional[dict]]:
        """Generate pedagogical feedback for teacher.

        Args:
            teacher_question: Latest teacher question
            student_response: Student's response
            recent_exchanges: Recent conversation context

        Returns:
            Tuple of (feedback_string or None, usage_dict or None)
            usage_dict contains: prompt_tokens, completion_tokens,
            total_tokens

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
            return None, None

        try:
            # Load dynamic prompt template (5-min cache, <10ms)
            template = await PromptManager.get_active_prompt(
                self.db_session, "tutor"
            )

            # Format with scenario context
            system_prompt = template.format(
                scenario_title=self.scenario_title,
                prompt=self.prompt,
                student_profile=self.student_profile,
            )

            # Build analysis context
            context = "Recent conversation:\n"
            for ex in recent_exchanges[-4:]:
                context += f"{ex['role'].upper()}: {ex['content']}\n"
            context += f"TEACHER: {teacher_question}\n"
            context += f"STUDENT: {student_response}\n"

            # Build input for Responses API (developer role)
            input_messages = [
                {"role": "developer", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{context}\n"
                        "교사를 위한 간단하고 건설적인 피드백을 한글로 제공해주세요."
                    ),
                },
            ]

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

            self.intervention_count += 1
            return content, usage_dict

        except (APIConnectionError, RateLimitError, APIError) as e:
            logger.error(f"TutorBot API error: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in TutorBot: {str(e)}")
            raise RuntimeError(
                f"Tutor feedback generation failed: {str(e)}"
            ) from e
