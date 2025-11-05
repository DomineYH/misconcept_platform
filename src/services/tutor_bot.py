"""TutorBot service for pedagogical feedback and intervention."""
from pathlib import Path
from openai import AsyncOpenAI

from src.config import config


class TutorBot:
    """Chatbot providing real-time pedagogical feedback."""

    def __init__(self):
        """Initialize TutorBot with system prompt."""
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.ANALYSIS_MODEL  # Can use faster model
        self.temperature = 0.3  # More consistent feedback

        # Load tutor system prompt
        prompt_path = (
            Path(__file__).parent.parent
            / "prompts"
            / "tutor_system.txt"
        )
        self.system_prompt = prompt_path.read_text()

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
