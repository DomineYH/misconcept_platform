from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Session

StaleReason = Literal["missing", "deleted", "ended"]


@dataclass(frozen=True, slots=True)
class StaleSessionError(Exception):
    session_id: int
    reason: StaleReason

    def __str__(self) -> str:
        return (
            f"session {self.session_id} is not writable "
            f"because it is {self.reason}"
        )


async def ensure_session_writable(
    db: AsyncSession,
    session_id: int,
) -> Session:
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .execution_options(populate_existing=True)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise StaleSessionError(session_id=session_id, reason="missing")
    if session.deleted_at is not None:
        raise StaleSessionError(session_id=session_id, reason="deleted")
    if session.ended_at is not None:
        raise StaleSessionError(session_id=session_id, reason="ended")
    return session


async def flush_with_stale_session_check(
    db: AsyncSession,
    session_id: int,
) -> None:
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        try:
            await ensure_session_writable(db, session_id)
        except StaleSessionError as stale_error:
            raise stale_error from exc
        raise
