"""Unit tests for admin bulk user creation helpers."""

import csv
import io
from typing import Any, Callable

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from src.api.schemas.user import UserCreate
from src.models.user import User
from src.models.user_group import UserGroup


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    """Build UTF-8 BOM CSV bytes with the approved header."""
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "username",
            "nickname",
            "password",
            "role",
            "group_name",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _resolve_helper(
    obj: Any,
    *names: str,
) -> Callable[..., Any]:
    """Return the first matching callable helper from module or service."""
    for name in names:
        candidate = getattr(obj, name, None)
        if callable(candidate):
            return candidate
    raise AttributeError(
        f"None of the expected helpers were found: {', '.join(names)}"
    )


@pytest.fixture
def bulk_api():
    """Load the bulk helper API without hard-coding one implementation shape."""
    module = pytest.importorskip("src.services.admin_user_bulk")
    service_cls = getattr(module, "AdminUserBulkService", None)
    service = service_cls() if service_cls else module
    return {
        "parse_pattern_username": _resolve_helper(
            service,
            "parse_pattern_username",
        ),
        "create_pattern_users": _resolve_helper(
            service,
            "create_pattern_users",
            "bulk_create_pattern_users",
        ),
        "import_csv": _resolve_helper(
            service,
            "import_csv",
            "import_users_csv",
            "bulk_import_csv",
        ),
    }


@pytest.fixture
async def test_group(async_session):
    """Create a reusable group for bulk-user tests."""
    group = UserGroup(
        name="Bulk Test Group",
        description="Group for bulk user tests",
    )
    async_session.add(group)
    await async_session.flush()
    return group


@pytest.mark.parametrize(
    ("value", "expected_prefix", "expected_number"),
    [
        ("teacher_1", "teacher", 1),
        ("teacher_batch_007", "teacher_batch", 7),
        ("A_42", "A", 42),
    ],
)
def test_parse_pattern_username_success(
    bulk_api,
    value: str,
    expected_prefix: str,
    expected_number: int,
):
    """Pattern usernames must parse as prefix + numeric suffix."""
    prefix, number = bulk_api["parse_pattern_username"](value)

    assert prefix == expected_prefix
    assert number == expected_number


@pytest.mark.parametrize(
    "value",
    ["teacher", "teacher-a", "teacher_", "_7", "teacher_7_extra"],
)
def test_parse_pattern_username_rejects_invalid_values(
    bulk_api,
    value: str,
):
    """Invalid pattern usernames must fail fast."""
    with pytest.raises(ValueError):
        bulk_api["parse_pattern_username"](value)


@pytest.mark.asyncio
async def test_create_pattern_users_skips_collisions_and_hits_requested_count(
    bulk_api,
    async_session,
    test_group: UserGroup,
):
    """Pattern mode must skip taken suffixes and still create N users."""
    taken_1 = User(
        username="teacher_1",
        nickname="teacher_1",
        role="teacher",
        group_id=test_group.id,
    )
    taken_1.set_password("existing123")
    taken_3 = User(
        username="teacher_3",
        nickname="teacher_3",
        role="teacher",
        group_id=test_group.id,
    )
    taken_3.set_password("existing123")
    async_session.add_all([taken_1, taken_3])
    await async_session.flush()

    summary = await bulk_api["create_pattern_users"](
        async_session,
        start_username="teacher_1",
        count=3,
        role="teacher",
        group_id=test_group.id,
    )

    created_users = (
        (
            await async_session.execute(
                select(User)
                .where(
                    User.username.in_(
                        ["teacher_2", "teacher_4", "teacher_5"]
                    )
                )
                .order_by(User.username)
            )
        )
        .scalars()
        .all()
    )

    assert summary["created_count"] == 3
    assert summary["failed_count"] == 0
    assert [user.username for user in created_users] == [
        "teacher_2",
        "teacher_4",
        "teacher_5",
    ]
    assert all(user.nickname == user.username for user in created_users)
    assert all(user.role == "teacher" for user in created_users)
    assert all(user.group_id == test_group.id for user in created_users)
    assert all(user.verify_password("0000") for user in created_users)


@pytest.mark.asyncio
async def test_import_csv_creates_valid_rows_and_maps_groups(
    bulk_api,
    async_session,
    test_group: UserGroup,
):
    """CSV mode must create valid rows and resolve group_name."""
    payload = _csv_bytes(
        [
            {
                "username": "csv_user_1",
                "nickname": "CSV One",
                "password": "0000",
                "role": "teacher",
                "group_name": test_group.name,
            },
            {
                "username": "csv_admin_1",
                "nickname": "CSV Admin",
                "password": "secret123",
                "role": "admin",
                "group_name": "",
            },
        ]
    )

    summary = await bulk_api["import_csv"](
        async_session,
        payload,
        filename="bulk-users.csv",
    )

    created_users = (
        (
            await async_session.execute(
                select(User)
                .where(User.username.in_(["csv_user_1", "csv_admin_1"]))
                .order_by(User.username)
            )
        )
        .scalars()
        .all()
    )
    created_by_username = {user.username: user for user in created_users}

    assert summary["created_count"] == 2
    assert summary["failed_count"] == 0
    assert created_by_username["csv_user_1"].group_id == test_group.id
    assert created_by_username["csv_user_1"].verify_password("0000")
    assert created_by_username["csv_admin_1"].group_id is None
    assert created_by_username["csv_admin_1"].role == "admin"
    assert created_by_username["csv_admin_1"].verify_password("secret123")


@pytest.mark.asyncio
async def test_import_csv_counts_row_failures(
    bulk_api,
    async_session,
    test_group: UserGroup,
):
    """CSV mode must fail bad rows without renumbering them."""
    existing = User(
        username="dup_user",
        nickname="Existing",
        role="teacher",
        group_id=test_group.id,
    )
    existing.set_password("existing123")
    async_session.add(existing)
    await async_session.flush()

    payload = _csv_bytes(
        [
            {
                "username": "dup_user",
                "nickname": "Duplicate",
                "password": "0000",
                "role": "teacher",
                "group_name": test_group.name,
            },
            {
                "username": "bad_group",
                "nickname": "Bad Group",
                "password": "0000",
                "role": "teacher",
                "group_name": "Missing Group",
            },
            {
                "username": "bad_role",
                "nickname": "Bad Role",
                "password": "0000",
                "role": "student",
                "group_name": "",
            },
            {
                "username": "ok_user",
                "nickname": "Okay",
                "password": "0000",
                "role": "teacher",
                "group_name": test_group.name,
            },
        ]
    )

    summary = await bulk_api["import_csv"](
        async_session,
        payload,
        filename="bulk-users.csv",
    )

    persisted_usernames = set(
        (
            await async_session.execute(
                select(User.username).where(
                    User.username.in_(
                        [
                            "dup_user",
                            "dup_user_1",
                            "bad_group",
                            "bad_role",
                            "ok_user",
                        ]
                    )
                )
            )
        )
        .scalars()
        .all()
    )

    assert summary["created_count"] == 1
    assert summary["failed_count"] == 3
    assert persisted_usernames == {"dup_user", "ok_user"}


@pytest.mark.asyncio
async def test_import_csv_rejects_payload_over_one_mebibyte_before_writes(
    bulk_api,
    async_session,
):
    """Guardrail must reject oversized CSV payloads before DB writes."""
    huge_field = "x" * (1024 * 1024)
    payload = (
        "username,nickname,password,role,group_name\n"
        f"too_big,{huge_field},0000,teacher,\n"
    ).encode("utf-8")

    with pytest.raises(ValueError, match="1 MiB"):
        await bulk_api["import_csv"](
            async_session,
            payload,
            filename="too-large.csv",
        )

    persisted = await async_session.scalar(
        select(User).where(User.username == "too_big")
    )
    assert persisted is None


@pytest.mark.asyncio
async def test_import_csv_rejects_more_than_1000_rows_before_writes(
    bulk_api,
    async_session,
):
    """Guardrail must reject CSV uploads with more than 1000 data rows."""
    rows = [
        {
            "username": f"bulk_{index}",
            "nickname": f"Bulk {index}",
            "password": "0000",
            "role": "teacher",
            "group_name": "",
        }
        for index in range(1001)
    ]

    with pytest.raises(ValueError, match="1000"):
        await bulk_api["import_csv"](
            async_session,
            _csv_bytes(rows),
            filename="too-many-rows.csv",
        )

    created_count = len(
        (
            await async_session.execute(
                select(User.username).where(User.username.like("bulk_%"))
            )
        )
        .scalars()
        .all()
    )
    assert created_count == 0


@pytest.mark.asyncio
async def test_bulk_password_rules_stay_separate_from_legacy_user_create_schema(
    bulk_api,
    async_session,
):
    """Bulk helpers may accept 4-char passwords without widening UserCreate."""
    with pytest.raises(ValidationError):
        UserCreate(
            username="legacy_short_pw",
            password="0000",
            nickname="짧은비번",
            role="teacher",
        )

    summary = await bulk_api["create_pattern_users"](
        async_session,
        start_username="bulkpw_1",
        count=1,
        role="teacher",
        group_id=None,
    )
    created = await async_session.scalar(
        select(User).where(User.username == "bulkpw_1")
    )

    assert summary["created_count"] == 1
    assert summary["failed_count"] == 0
    assert created is not None
    assert created.verify_password("0000")
