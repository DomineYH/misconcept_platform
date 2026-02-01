"""Shared helper functions for session management."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Session, User


async def load_session(
    session_id: int,
    user: User,
    db: AsyncSession,
) -> Session:
    """Load session and validate ownership.

    Args:
        session_id: Session ID to load
        user: Current user from auth
        db: Database session

    Returns:
        Session object

    Raises:
        HTTPException: 404 if not found or wrong owner, 403 if forbidden
    """
    result = await db.execute(
        select(Session).where(
            Session.id == session_id, Session.deleted_at.is_(None)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return session


async def mark_session_ended(
    session: Session,
    db: AsyncSession,
    *,
    force: bool = False,
) -> tuple[datetime, bool]:
    """Mark session as ended by setting ended_at timestamp.

    Args:
        session: Session to mark as ended
        db: Database session
        force: If True, allows idempotent behavior (no error if already ended)

    Returns:
        Tuple of (ended_at timestamp, was_already_ended boolean)

    Raises:
        HTTPException: 400 if already ended and force=False
    """
    if session.ended_at:
        if not force:
            raise HTTPException(
                status_code=400, detail="Session already ended"
            )
        return session.ended_at, True

    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    return session.ended_at, False
