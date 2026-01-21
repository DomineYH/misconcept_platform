"""
CSV export service for session data (T062-T064).

Generates UTF-8 CSV files with anonymized student identifiers
and session summary rows.
"""

import csv
import hashlib
import io
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.message import Message
from src.models.question_analysis import QuestionAnalysis
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.session_summary import SessionSummary
from src.models.user import User


logger = logging.getLogger(__name__)


class CSVExporter:
    """
    Session data export service with anonymization.

    Generates CSV exports with columns:
    session_id, scenario_title, student_hash, timestamp,
    role, content, label, confidence, feedback
    """

    @staticmethod
    def _anonymize_student(student_uid: str, session_salt: str) -> str:
        """
        Anonymize student identifier using SHA-256 hash.

        Args:
            student_uid: Original student identifier
            session_salt: Session-specific salt

        Returns:
            Hexadecimal hash string (64 characters)
        """
        combined = f"{student_uid}:{session_salt}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    async def export_session(self, session_id: int, db: AsyncSession) -> str:
        """
        Export single session to CSV format.

        Args:
            session_id: Session identifier
            db: Database session

        Returns:
            CSV content as string

        Raises:
            ValueError: If session not found
        """
        # Load session with relationships
        result = await db.execute(
            select(Session)
            .where(Session.id == session_id)
            .options(
                # Eager load relationships
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Load related data
        teacher_result = await db.execute(
            select(User).where(User.id == session.teacher_id)
        )
        teacher = teacher_result.scalar_one()

        scenario_result = await db.execute(
            select(Scenario).where(Scenario.id == session.scenario_id)
        )
        scenario = scenario_result.scalar_one()

        messages_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = messages_result.scalars().all()

        # Load question analyses
        analyses_result = await db.execute(
            select(QuestionAnalysis)
            .join(Message)
            .where(Message.session_id == session_id)
        )
        analyses = {a.message_id: a for a in analyses_result.scalars().all()}

        # Load session summary
        summary_result = await db.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id
            )
        )
        summary = summary_result.scalar_one_or_none()

        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "session_id",
                "scenario_title",
                "student_hash",
                "timestamp",
                "role",
                "content",
                "label",
                "confidence",
                "feedback",
            ],
        )
        writer.writeheader()

        # Anonymize student
        session_salt = str(session.started_at.timestamp())
        student_hash = self._anonymize_student(
            teacher.student_uid, session_salt
        )

        # Write message rows
        for msg in messages:
            analysis = analyses.get(msg.id)
            writer.writerow(
                {
                    "session_id": session_id,
                    "scenario_title": scenario.title,
                    "student_hash": student_hash,
                    "timestamp": msg.created_at.isoformat(),
                    "role": msg.role,
                    "content": msg.content,
                    "label": analysis.label if analysis else "",
                    "confidence": (
                        f"{analysis.confidence:.2f}"
                        if analysis and analysis.confidence
                        else ""
                    ),
                    "feedback": "",
                }
            )

        # Write summary row
        if summary:
            writer.writerow(
                {
                    "session_id": session_id,
                    "scenario_title": scenario.title,
                    "student_hash": student_hash,
                    "timestamp": summary.created_at.isoformat(),
                    "role": "summary",
                    "content": "Session Summary",
                    "label": "",
                    "confidence": "",
                    "feedback": summary.feedback or "",
                }
            )

        return output.getvalue()

    async def export_multiple_sessions(
        self, session_ids: List[int], db: AsyncSession
    ) -> str:
        """
        Export multiple sessions to single CSV.

        Args:
            session_ids: List of session identifiers
            db: Database session

        Returns:
            Combined CSV content as string
        """
        all_rows = []

        for session_id in session_ids:
            try:
                csv_content = await self.export_session(session_id, db)
                # Skip header for subsequent sessions
                lines = csv_content.strip().split("\n")
                if not all_rows:
                    all_rows.extend(lines)  # Include header
                else:
                    all_rows.extend(lines[1:])  # Skip header
            except ValueError as e:
                logger.warning(f"Skipping session {session_id}: {e}")
                continue

        return "\n".join(all_rows)

    async def export_session_admin(
        self, session_id: int, db: AsyncSession
    ) -> str:
        """Admin export with raw teacher info and meta_json."""
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        teacher_result = await db.execute(
            select(User).where(User.id == session.teacher_id)
        )
        teacher = teacher_result.scalar_one()

        scenario_result = await db.execute(
            select(Scenario).where(Scenario.id == session.scenario_id)
        )
        scenario = scenario_result.scalar_one()

        messages_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = messages_result.scalars().all()

        analyses_result = await db.execute(
            select(QuestionAnalysis)
            .join(Message)
            .where(Message.session_id == session_id)
        )
        analyses = {a.message_id: a for a in analyses_result.scalars().all()}

        summary_result = await db.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id
            )
        )
        summary = summary_result.scalar_one_or_none()

        output = io.StringIO()
        fieldnames = [
            "session_id",
            "scenario_id",
            "scenario_title",
            "teacher_id",
            "teacher_student_uid",
            "teacher_nickname",
            "session_started_at",
            "session_ended_at",
            "message_id",
            "message_created_at",
            "role",
            "content",
            "label",
            "confidence",
            "meta_json",
            "feedback",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for msg in messages:
            analysis = analyses.get(msg.id)
            writer.writerow(
                {
                    "session_id": session_id,
                    "scenario_id": scenario.id,
                    "scenario_title": scenario.title,
                    "teacher_id": teacher.id,
                    "teacher_student_uid": teacher.student_uid,
                    "teacher_nickname": teacher.nickname,
                    "session_started_at": session.started_at.isoformat(),
                    "session_ended_at": (
                        session.ended_at.isoformat() if session.ended_at else ""
                    ),
                    "message_id": msg.id,
                    "message_created_at": msg.created_at.isoformat(),
                    "role": msg.role,
                    "content": msg.content,
                    "label": analysis.label if analysis else "",
                    "confidence": (
                        f"{analysis.confidence:.2f}"
                        if analysis and analysis.confidence
                        else ""
                    ),
                    "meta_json": analysis.meta_json if analysis else "",
                    "feedback": "",
                }
            )

        if summary:
            writer.writerow(
                {
                    "session_id": session_id,
                    "scenario_id": scenario.id,
                    "scenario_title": scenario.title,
                    "teacher_id": teacher.id,
                    "teacher_student_uid": teacher.student_uid,
                    "teacher_nickname": teacher.nickname,
                    "session_started_at": session.started_at.isoformat(),
                    "session_ended_at": (
                        session.ended_at.isoformat() if session.ended_at else ""
                    ),
                    "message_id": "",
                    "message_created_at": summary.created_at.isoformat(),
                    "role": "summary",
                    "content": "Session Summary",
                    "label": "",
                    "confidence": "",
                    "meta_json": "",
                    "feedback": summary.feedback or "",
                }
            )

        return output.getvalue()

    async def export_multiple_sessions_admin(
        self, session_ids: List[int], db: AsyncSession
    ) -> str:
        """Admin bulk export with raw teacher info and meta_json."""
        all_rows: List[str] = []

        for session_id in session_ids:
            try:
                csv_content = await self.export_session_admin(session_id, db)
                lines = csv_content.strip().split("\n")
                if not all_rows:
                    all_rows.extend(lines)
                else:
                    all_rows.extend(lines[1:])
            except ValueError as e:
                logger.warning(f"Skipping session {session_id}: {e}")
                continue

        return "\n".join(all_rows)
