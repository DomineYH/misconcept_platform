"""SessionManager service for orchestrating dialogue flow."""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Session, Message, Scenario
from src.services.student_bot import StudentBot
from src.services.tutor_bot import TutorBot


class SessionManager:
    """Orchestrates teacher-student-tutor dialogue interactions."""

    def __init__(self, db_session: AsyncSession, session_id: int):
        """Initialize SessionManager for specific session.

        Args:
            db_session: Database session
            session_id: Dialogue session ID
        """
        self.db = db_session
        self.session_id = session_id
        self.student_bot = None
        self.tutor_bot = TutorBot()

    async def initialize(self) -> None:
        """Load session and initialize StudentBot with scenario."""
        # Load session and scenario
        result = await self.db.execute(
            select(Session).where(Session.id == self.session_id)
        )
        session = result.scalar_one()

        result = await self.db.execute(
            select(Scenario).where(Scenario.id == session.scenario_id)
        )
        scenario = result.scalar_one()

        # Initialize StudentBot with scenario context
        self.student_bot = StudentBot(
            scenario_prompt=scenario.prompt,
            scenario_title=scenario.title,
            student_profile=scenario.student_profile or "Grade 5 student",
        )

    async def process_teacher_message(
        self, teacher_content: str
    ) -> list[Message]:
        """Process teacher message and generate bot responses.

        Args:
            teacher_content: Teacher's question/message

        Returns:
            List of new Message objects (teacher, student, optional tutor)
        """
        if not self.student_bot:
            await self.initialize()

        new_messages = []

        # 1. Save teacher message
        teacher_msg = Message(
            session_id=self.session_id,
            role="teacher",
            content=teacher_content,
        )
        self.db.add(teacher_msg)
        await self.db.flush()  # Get ID without commit
        new_messages.append(teacher_msg)

        # 2. Load conversation history
        history = await self._get_conversation_history()

        # 3. Generate student response
        student_content = await self.student_bot.generate_response(
            teacher_content, history
        )
        student_msg = Message(
            session_id=self.session_id,
            role="student",
            content=student_content,
        )
        self.db.add(student_msg)
        await self.db.flush()
        new_messages.append(student_msg)

        # 4. Check if tutor should intervene
        tutor_feedback = await self.tutor_bot.generate_feedback(
            teacher_content, student_content, history
        )

        if tutor_feedback:
            tutor_msg = Message(
                session_id=self.session_id,
                role="tutor",
                content=tutor_feedback,
            )
            self.db.add(tutor_msg)
            await self.db.flush()
            new_messages.append(tutor_msg)

        # 5. Commit all messages
        await self.db.commit()

        # Refresh to get created_at timestamps
        for msg in new_messages:
            await self.db.refresh(msg)

        return new_messages

    async def _get_conversation_history(self) -> list[dict]:
        """Retrieve conversation history for context.

        Returns:
            List of message dicts with role and content
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == self.session_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        return [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

    async def end_session(self) -> None:
        """Mark session as ended."""
        result = await self.db.execute(
            select(Session).where(Session.id == self.session_id)
        )
        session = result.scalar_one()

        session.ended_at = datetime.utcnow()
        await self.db.commit()
