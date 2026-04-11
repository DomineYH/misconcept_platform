"""Unit tests for bulk user registration."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.user import BulkUserEntry
from src.models.user import User
from src.models.user_group import UserGroup
from src.services.admin_user_bulk import register_bulk_users


@pytest.mark.asyncio
async def test_register_creates_users(db_session: AsyncSession):
    group = UserGroup(name="TestGroup")
    db_session.add(group)
    await db_session.flush()

    users = [
        BulkUserEntry(username="new_user_1", nickname="새유저1", role="teacher", group_id=group.id),
        BulkUserEntry(username="new_user_2", nickname="새유저2", role="admin", group_id=None),
    ]
    result = await register_bulk_users(users, db_session)

    assert result.success_count == 2
    assert result.fail_count == 0
    assert result.failures == []

    created = (await db_session.execute(
        select(User).where(User.username.in_(["new_user_1", "new_user_2"]))
    )).scalars().all()
    created_map = {u.username: u for u in created}

    assert created_map["new_user_1"].nickname == "새유저1"
    assert created_map["new_user_1"].group_id == group.id
    assert created_map["new_user_1"].verify_password("00000000")
    assert created_map["new_user_2"].role == "admin"
    assert created_map["new_user_2"].group_id is None


@pytest.mark.asyncio
async def test_register_skips_duplicate_username(db_session: AsyncSession):
    existing = User(username="taken_user", nickname="기존유저", role="teacher")
    existing.set_password("test1234")
    db_session.add(existing)
    await db_session.flush()

    users = [
        BulkUserEntry(username="taken_user", nickname="중복시도"),
        BulkUserEntry(username="fresh_user", nickname="새유저"),
    ]
    result = await register_bulk_users(users, db_session)

    assert result.success_count == 1
    assert result.fail_count == 1
    assert result.failures[0].username == "taken_user"
    assert "이미 존재" in result.failures[0].reason


@pytest.mark.asyncio
async def test_register_empty_list(db_session: AsyncSession):
    result = await register_bulk_users([], db_session)

    assert result.success_count == 0
    assert result.fail_count == 0
