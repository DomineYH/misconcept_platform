"""FastAPI dependency injection for database and auth."""

from typing import AsyncGenerator
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import AsyncSessionLocal


class AuthenticationRequired(Exception):
    """Exception raised when authentication is required."""

    def __init__(self, redirect_url: str = "/login"):
        self.redirect_url = redirect_url
        super().__init__("Authentication required")


async def get_db_session() -> AsyncGenerator[
    AsyncSession, None
]:
    """
    Provide database session for request scope.

    Yields:
        AsyncSession: Database session with transaction handling.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get current user from session.

    Args:
        request: FastAPI Request object
        db: Database session

    Returns:
        User: User model instance

    Raises:
        HTTPException: If not authenticated
    """
    from src.models.user import User

    # Get user_id from session
    user_id = request.session.get("user_id")
    if not user_id:
        raise AuthenticationRequired(redirect_url="/login")

    # Query user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
