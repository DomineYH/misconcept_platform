"""Bulk user creation helpers for admin routes."""

from __future__ import annotations

import csv
import io
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.user import (
    BulkCreateError,
    BulkCreateSummary,
    BulkCsvRow,
    BulkPatternCreate,
)
from src.models.user import User
from src.models.user_group import UserGroup

PATTERN_USERNAME_RE = re.compile(
    r"^(?P<prefix>[A-Za-z0-9_]+)_(?P<number>\d+)$"
)
MAX_CSV_FILE_SIZE = 1024 * 1024
MAX_CSV_DATA_ROWS = 1000
CSV_HEADER = [
    "username",
    "nickname",
    "password",
    "role",
    "group_name",
]
MAX_ERROR_SAMPLES = 20


def _build_summary(
    created_usernames: list[str],
    errors: list[BulkCreateError],
) -> BulkCreateSummary:
    return BulkCreateSummary(
        created_count=len(created_usernames),
        failed_count=len(errors),
        created_usernames=created_usernames,
        errors=errors[:MAX_ERROR_SAMPLES],
    )


def validate_pattern_username(start_username: str) -> tuple[str, int, int]:
    """Parse a pattern username in prefix_number format."""
    match = PATTERN_USERNAME_RE.match(start_username)
    if not match:
        raise ValueError(
            "시작 사용자 ID는 prefix_number 형식이어야 합니다."
        )

    prefix = match.group("prefix")
    number = match.group("number")
    return prefix, int(number), len(number)


async def create_pattern_users(
    db: AsyncSession,
    data: BulkPatternCreate,
) -> BulkCreateSummary:
    """Create users from a prefix_number pattern, skipping duplicates."""
    prefix, next_number, width = validate_pattern_username(
        data.start_username
    )

    created_usernames: list[str] = []

    while len(created_usernames) < data.count:
        username = f"{prefix}_{next_number:0{width}d}"
        next_number += 1

        existing = await db.scalar(
            select(User.id).where(User.username == username)
        )
        if existing is not None:
            continue

        user = User(
            username=username,
            nickname=username,
            role=data.role,
            group_id=data.group_id,
        )
        user.set_password("0000")
        db.add(user)
        await db.flush()
        created_usernames.append(username)

    return _build_summary(created_usernames, [])


async def build_group_name_map(
    db: AsyncSession,
) -> dict[str, int]:
    result = await db.execute(select(UserGroup).order_by(UserGroup.id))
    groups = result.scalars().all()
    return {group.name: group.id for group in groups}


def render_bulk_template_csv() -> str:
    """Return the CSV template content without BOM."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    writer.writerow(["teacher_001", "교사1", "0000", "teacher", ""])
    return output.getvalue()


def _validate_header(fieldnames: Iterable[str] | None) -> None:
    names = list(fieldnames or [])
    if names != CSV_HEADER:
        raise ValueError(
            "CSV 헤더는 username,nickname,password,role,group_name 이어야 합니다."
        )


def _decode_csv_content(file_bytes: bytes) -> str:
    if len(file_bytes) > MAX_CSV_FILE_SIZE:
        raise ValueError(
            "CSV 파일은 1 MiB 이하여야 합니다."
        )

    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "CSV 파일은 UTF-8 인코딩이어야 합니다."
        ) from exc


async def import_csv_users(
    db: AsyncSession,
    file_bytes: bytes,
) -> BulkCreateSummary:
    """Import users from CSV rows, failing duplicate usernames per row."""
    csv_text = _decode_csv_content(file_bytes)
    reader = csv.DictReader(io.StringIO(csv_text))
    _validate_header(reader.fieldnames)

    rows = list(reader)
    if len(rows) > MAX_CSV_DATA_ROWS:
        raise ValueError(
            "CSV 데이터 행은 1000개를 초과할 수 없습니다."
        )

    group_name_map = await build_group_name_map(db)
    existing_result = await db.execute(select(User.username))
    known_usernames = set(existing_result.scalars().all())

    created_usernames: list[str] = []
    errors: list[BulkCreateError] = []

    for index, row in enumerate(rows, start=2):
        try:
            data = BulkCsvRow.model_validate(row)
        except Exception as exc:  # pydantic validation error
            errors.append(
                BulkCreateError(
                    row=index,
                    username=row.get("username") or None,
                    message=str(exc).splitlines()[0],
                )
            )
            continue

        if data.username in known_usernames:
            errors.append(
                BulkCreateError(
                    row=index,
                    username=data.username,
                    message="이미 존재하는 사용자 ID입니다.",
                )
            )
            continue

        group_id = None
        if data.group_name:
            group_id = group_name_map.get(data.group_name)
            if group_id is None:
                errors.append(
                    BulkCreateError(
                        row=index,
                        username=data.username,
                        message="존재하지 않는 그룹명입니다.",
                    )
                )
                continue

        user = User(
            username=data.username,
            nickname=data.nickname,
            role=data.role,
            group_id=group_id,
        )
        user.set_password(data.password)
        db.add(user)
        await db.flush()

        known_usernames.add(data.username)
        created_usernames.append(data.username)

    return _build_summary(created_usernames, errors)
