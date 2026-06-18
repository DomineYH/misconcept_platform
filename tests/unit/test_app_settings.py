"""Tests for app_settings service (Issue #55 synthesis toggle)."""

import pytest

from src.services.app_settings import (
    is_synthesis_enabled,
    set_synthesis_enabled,
)


@pytest.mark.asyncio
async def test_default_is_true_when_no_row(async_db_session):
    """Synthesis defaults to ON when no setting row exists."""
    assert await is_synthesis_enabled(async_db_session) is True


@pytest.mark.asyncio
async def test_set_false_then_read(async_db_session):
    """Setting to False persists and reads back as False."""
    await set_synthesis_enabled(async_db_session, False)
    assert await is_synthesis_enabled(async_db_session) is False


@pytest.mark.asyncio
async def test_toggle_back_to_true(async_db_session):
    """Toggling False then True reads back True (upsert path)."""
    await set_synthesis_enabled(async_db_session, False)
    await set_synthesis_enabled(async_db_session, True)
    assert await is_synthesis_enabled(async_db_session) is True
