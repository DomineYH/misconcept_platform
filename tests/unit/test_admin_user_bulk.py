"""Unit tests for admin bulk user helpers and schemas."""

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.user import BulkCsvRow, BulkPatternCreate, UserCreate
from src.models.user import User
from src.models.user_group import UserGroup
from src.services.admin_user_bulk import (
    CSV_HEADER,
    create_pattern_users,
    import_csv_users,
    render_bulk_template_csv,
    validate_pattern_username,
)


def test_validate_pattern_username_success():
    """Valid prefix_number usernames should parse into parts."""
    prefix, number, width = validate_pattern_username("teacher_001")

    assert prefix == "teacher"
    assert number == 1
    assert width == 3


def test_validate_pattern_username_rejects_invalid_format():
    """Pattern usernames must include an underscore and numeric suffix."""
    with pytest.raises(ValueError, match="prefix_number"):
        validate_pattern_username("teacher001")


@pytest.mark.asyncio
async def test_create_pattern_users_skips_collisions_and_sets_defaults(
    db_session: AsyncSession,
):
    """Pattern mode should skip duplicates and still create target count."""
    group = UserGroup(name="Bulk Group")
    db_session.add(group)
    await db_session.flush()

    existing = User(
        username="teacher_002",
        nickname="existing",
        role="teacher",
        group_id=group.id,
    )
    existing.set_password("test1234")
    db_session.add(existing)
    await db_session.flush()

    summary = await create_pattern_users(
        db_session,
        BulkPatternCreate(
            start_username="teacher_001",
            count=3,
            role="teacher",
            group_id=group.id,
        ),
    )

    users = (
        (await db_session.execute(
            select(User).where(User.username.like("teacher_%")).order_by(User.username)
        ))
        .scalars()
        .all()
    )
    usernames = [user.username for user in users]

    assert summary.created_count == 3
    assert summary.failed_count == 0
    assert summary.created_usernames == [
        "teacher_001",
        "teacher_003",
        "teacher_004",
    ]
    assert usernames == [
        "teacher_001",
        "teacher_002",
        "teacher_003",
        "teacher_004",
    ]
    created = {
        user.username: user
        for user in users
        if user.username != "teacher_002"
    }
    assert all(user.nickname == username for username, user in created.items())
    assert all(user.verify_password("0000") for user in created.values())
    assert all(user.group_id == group.id for user in created.values())


@pytest.mark.asyncio
async def test_import_csv_users_tracks_success_and_row_failures(
    db_session: AsyncSession,
):
    """CSV mode should create valid rows and report bad rows."""
    group = UserGroup(name="Alpha")
    db_session.add(group)

    existing = User(username="dup_user", nickname="Dup", role="teacher")
    existing.set_password("test1234")
    db_session.add(existing)
    await db_session.flush()

    csv_bytes = (
        "username,nickname,password,role,group_name\n"
        "fresh_user,새 사용자,0000,teacher,Alpha\n"
        "dup_user,중복,0000,teacher,Alpha\n"
        "ghost_user,없는 그룹,0000,teacher,Missing\n"
    ).encode("utf-8")

    summary = await import_csv_users(db_session, csv_bytes)

    assert summary.created_count == 1
    assert summary.failed_count == 2
    assert summary.created_usernames == ["fresh_user"]
    assert {error.username for error in summary.errors} == {
        "dup_user",
        "ghost_user",
    }

    created_user = await db_session.scalar(
        select(User).where(User.username == "fresh_user")
    )
    assert created_user is not None
    assert created_user.nickname == "새 사용자"
    assert created_user.group_id == group.id
    assert created_user.verify_password("0000")


@pytest.mark.asyncio
async def test_import_csv_users_rejects_more_than_1000_rows(
    db_session: AsyncSession,
):
    """CSV imports should enforce the 1000 data-row guardrail before writes."""
    rows = ["username,nickname,password,role,group_name"]
    rows.extend(
        f"user_{i:04d},닉네임{i},0000,teacher," for i in range(1001)
    )
    csv_bytes = "\n".join(rows).encode("utf-8")

    with pytest.raises(ValueError, match="1000"):
        await import_csv_users(db_session, csv_bytes)

    count = await db_session.scalar(select(func.count(User.id)))
    assert count == 0


def test_render_bulk_template_csv_has_exact_header():
    """Template CSV should expose the exact approved header."""
    template = render_bulk_template_csv().splitlines()

    assert template[0] == ",".join(CSV_HEADER)


def test_bulk_password_schema_is_separate_from_legacy_user_create():
    """Bulk CSV rows accept 0000 without widening legacy rules."""
    row = BulkCsvRow(
        username="bulk_001",
        nickname="벌크",
        password="0000",
        role="teacher",
        group_name="",
    )

    assert row.password == "0000"
    assert row.group_name is None

    with pytest.raises(ValidationError):
        UserCreate(
            username="single_001",
            nickname="단건",
            password="0000",
            role="teacher",
        )
