"""Unit tests for bulk user validation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.user_group import UserGroup
from src.services.admin_user_bulk import validate_bulk_users


@pytest.mark.asyncio
async def test_valid_rows_pass(db_session: AsyncSession):
    group = UserGroup(name="1학년")
    db_session.add(group)
    await db_session.flush()

    rows = [
        {"username": "kim_01", "nickname": "김민준", "role": "teacher", "group": "1학년"},
        {"username": "lee_02", "nickname": "이소연", "role": "", "group": ""},
    ]
    result = await validate_bulk_users(rows, db_session)

    assert result.summary["total"] == 2
    assert result.summary["valid"] == 2
    assert result.summary["error"] == 0
    assert result.rows[0].group_id == group.id
    assert result.rows[0].group_name == "1학년"
    assert result.rows[1].role == "teacher"
    assert result.rows[1].group_id is None
    assert len(result.groups) >= 1


@pytest.mark.asyncio
async def test_duplicate_username_in_db(db_session: AsyncSession):
    existing = User(username="existing_user", nickname="기존", role="teacher")
    existing.set_password("test1234")
    db_session.add(existing)
    await db_session.flush()

    rows = [{"username": "existing_user", "nickname": "중복", "role": "", "group": ""}]
    result = await validate_bulk_users(rows, db_session)

    assert result.summary["error"] == 1
    assert "이미 존재하는 사용자 ID" in result.rows[0].errors


@pytest.mark.asyncio
async def test_duplicate_username_within_csv(db_session: AsyncSession):
    rows = [
        {"username": "dup_user", "nickname": "첫번째", "role": "", "group": ""},
        {"username": "dup_user", "nickname": "두번째", "role": "", "group": ""},
    ]
    result = await validate_bulk_users(rows, db_session)

    assert result.rows[0].errors == []
    assert "CSV 내 중복된 사용자 ID" in result.rows[1].errors


@pytest.mark.asyncio
async def test_invalid_username_format(db_session: AsyncSession):
    rows = [
        {"username": "ab", "nickname": "짧은", "role": "", "group": ""},
        {"username": "bad user!", "nickname": "특수문자", "role": "", "group": ""},
    ]
    result = await validate_bulk_users(rows, db_session)

    assert any("3자" in e for e in result.rows[0].errors)
    assert any("영문" in e for e in result.rows[1].errors)


@pytest.mark.asyncio
async def test_invalid_nickname(db_session: AsyncSession):
    rows = [{"username": "user_01", "nickname": "가", "role": "", "group": ""}]
    result = await validate_bulk_users(rows, db_session)

    assert any("2자" in e for e in result.rows[0].errors)


@pytest.mark.asyncio
async def test_invalid_role(db_session: AsyncSession):
    rows = [{"username": "user_01", "nickname": "닉네임", "role": "superadmin", "group": ""}]
    result = await validate_bulk_users(rows, db_session)

    assert any("유효하지 않은 역할" in e for e in result.rows[0].errors)


@pytest.mark.asyncio
async def test_invalid_group_name(db_session: AsyncSession):
    rows = [{"username": "user_01", "nickname": "닉네임", "role": "", "group": "존재하지않는그룹"}]
    result = await validate_bulk_users(rows, db_session)

    assert any("존재하지 않는 그룹" in e for e in result.rows[0].errors)


@pytest.mark.asyncio
async def test_groups_list_returned(db_session: AsyncSession):
    g1 = UserGroup(name="A그룹")
    g2 = UserGroup(name="B그룹")
    db_session.add_all([g1, g2])
    await db_session.flush()

    rows = [{"username": "user_01", "nickname": "닉네임", "role": "", "group": ""}]
    result = await validate_bulk_users(rows, db_session)

    group_names = {g["name"] for g in result.groups}
    assert "A그룹" in group_names
    assert "B그룹" in group_names
