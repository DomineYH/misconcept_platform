"""Tests for SQLite PRAGMA foreign_keys=ON (Issue #28, E10)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_foreign_keys_pragma_on(db_session: AsyncSession):
    """PRAGMA foreign_keys must be ON for every connection."""
    result = await db_session.execute(text("PRAGMA foreign_keys"))
    value = result.scalar()
    assert value == 1, f"PRAGMA foreign_keys should be 1 (ON), got {value}"
