# Bulk User Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CSV-based bulk user registration with preview/edit/register flow to admin user management.

**Architecture:** New service module `admin_user_bulk.py` handles CSV parsing, validation, and registration. Three new endpoints are added to the existing `admin_users.py` router. The users.html template gains a multi-step modal (upload → preview → results) with client-side editing powered by vanilla JS.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, Pydantic v2, Jinja2, vanilla JavaScript

---

### Task 0: Clean Up Old Bulk User Code

The previous bulk user implementation was deleted but its tests remain, importing non-existent modules. Remove these stale files before building the new implementation.

**Files:**
- Delete: `tests/unit/test_admin_user_bulk.py`
- Delete: `tests/contract/test_admin_user_bulk_endpoints.py`

- [ ] **Step 1: Delete stale test files**

```bash
rm tests/unit/test_admin_user_bulk.py
rm tests/contract/test_admin_user_bulk_endpoints.py
```

- [ ] **Step 2: Verify tests pass without old files**

Run: `pytest tests/ --co -q 2>&1 | tail -5`
Expected: No collection errors from missing imports

- [ ] **Step 3: Commit**

```bash
git add -u tests/unit/test_admin_user_bulk.py tests/contract/test_admin_user_bulk_endpoints.py
git commit -m "chore: remove stale bulk user tests from previous implementation"
```

---

### Task 1: Pydantic Schemas for Bulk Operations

**Files:**
- Modify: `src/api/schemas/user.py:42` (append after AdminUserResponse)
- Modify: `src/api/schemas/__init__.py:217-231` (add to imports and __all__)
- Test: `tests/unit/test_bulk_user_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_bulk_user_schemas.py`:

```python
"""Unit tests for bulk user Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.api.schemas.user import (
    BulkPreviewRow,
    BulkPreviewResponse,
    BulkUserEntry,
    BulkRegisterRequest,
    BulkFailure,
    BulkRegisterResponse,
)


class TestBulkPreviewRow:
    def test_defaults(self):
        row = BulkPreviewRow(row_num=1, username="kim", nickname="김")
        assert row.role == "teacher"
        assert row.group_name is None
        assert row.group_id is None
        assert row.errors == []

    def test_with_errors(self):
        row = BulkPreviewRow(
            row_num=2,
            username="bad",
            nickname="나쁜",
            errors=["이미 존재하는 사용자 ID"],
        )
        assert len(row.errors) == 1


class TestBulkPreviewResponse:
    def test_structure(self):
        resp = BulkPreviewResponse(
            rows=[
                BulkPreviewRow(
                    row_num=1, username="a", nickname="가"
                )
            ],
            groups=[{"id": 1, "name": "G1"}],
            summary={"total": 1, "valid": 1, "error": 0},
        )
        assert resp.summary["total"] == 1
        assert len(resp.rows) == 1


class TestBulkUserEntry:
    def test_defaults(self):
        entry = BulkUserEntry(username="u1", nickname="닉")
        assert entry.role == "teacher"
        assert entry.group_id is None

    def test_with_group(self):
        entry = BulkUserEntry(
            username="u2",
            nickname="닉2",
            role="admin",
            group_id=5,
        )
        assert entry.role == "admin"
        assert entry.group_id == 5


class TestBulkRegisterRequest:
    def test_accepts_list(self):
        req = BulkRegisterRequest(
            users=[
                BulkUserEntry(username="a", nickname="가"),
                BulkUserEntry(username="b", nickname="나"),
            ]
        )
        assert len(req.users) == 2


class TestBulkRegisterResponse:
    def test_structure(self):
        resp = BulkRegisterResponse(
            success_count=2,
            fail_count=1,
            failures=[
                BulkFailure(
                    username="dup",
                    nickname="중복",
                    reason="이미 존재하는 사용자 ID",
                )
            ],
        )
        assert resp.success_count == 2
        assert resp.failures[0].reason == "이미 존재하는 사용자 ID"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bulk_user_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'BulkPreviewRow'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/api/schemas/user.py` after the `AdminUserResponse` class (after line 41):

```python


class BulkPreviewRow(BaseModel):
    """Single row in bulk upload preview."""

    row_num: int
    username: str
    nickname: str
    role: str = "teacher"
    group_name: str | None = None
    group_id: int | None = None
    errors: list[str] = []


class BulkPreviewResponse(BaseModel):
    """Response from CSV preview endpoint."""

    rows: list[BulkPreviewRow]
    groups: list[dict]
    summary: dict


class BulkUserEntry(BaseModel):
    """Single user entry for bulk registration."""

    username: str
    nickname: str
    role: str = "teacher"
    group_id: int | None = None


class BulkRegisterRequest(BaseModel):
    """Request body for bulk user registration."""

    users: list[BulkUserEntry]


class BulkFailure(BaseModel):
    """Single failure entry in bulk registration result."""

    username: str
    nickname: str
    reason: str


class BulkRegisterResponse(BaseModel):
    """Response from bulk registration endpoint."""

    success_count: int
    fail_count: int
    failures: list[BulkFailure]
```

Update `src/api/schemas/__init__.py` — add to the import from `src.api.schemas.user`:

```python
from src.api.schemas.user import (
    AdminUserResponse,
    BulkFailure,
    BulkPreviewResponse,
    BulkPreviewRow,
    BulkRegisterRequest,
    BulkRegisterResponse,
    BulkUserEntry,
    UserCreate,
    UserUpdate,
)
```

And add to `__all__`:

```python
__all__ = [
    "LabelItem",
    "FrameworkCreateWeb",
    "FrameworkUpdateWeb",
    "AdminFrameworkResponse",
    "ScenarioCreate",
    "ScenarioUpdate",
    "AdminScenarioResponse",
    "UserCreate",
    "UserUpdate",
    "AdminUserResponse",
    "BulkPreviewRow",
    "BulkPreviewResponse",
    "BulkUserEntry",
    "BulkRegisterRequest",
    "BulkFailure",
    "BulkRegisterResponse",
    "GroupCreate",
    "GroupUpdate",
    "AdminGroupResponse",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bulk_user_schemas.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/schemas/user.py src/api/schemas/__init__.py tests/unit/test_bulk_user_schemas.py
git commit -m "feat: add Pydantic schemas for bulk user upload"
```

---

### Task 2: Service — CSV Parsing (`parse_csv`)

**Files:**
- Create: `src/services/admin_user_bulk.py`
- Test: `tests/unit/test_bulk_user_parse_csv.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_bulk_user_parse_csv.py`:

```python
"""Unit tests for CSV parsing in bulk user service."""

import pytest

from src.services.admin_user_bulk import parse_csv


class TestParseCsv:
    def test_valid_utf8_csv(self):
        csv_bytes = (
            "username,nickname,role,group\n"
            "kim_minjun,김민준,teacher,1학년\n"
            "lee_soyeon,이소연,,\n"
        ).encode("utf-8")

        rows = parse_csv(csv_bytes)

        assert len(rows) == 2
        assert rows[0]["username"] == "kim_minjun"
        assert rows[0]["nickname"] == "김민준"
        assert rows[0]["role"] == "teacher"
        assert rows[0]["group"] == "1학년"
        assert rows[1]["role"] == ""
        assert rows[1]["group"] == ""

    def test_utf8_bom_csv(self):
        csv_bytes = (
            "\ufeffusername,nickname,role,group\n"
            "user1,닉네임1,,\n"
        ).encode("utf-8")

        rows = parse_csv(csv_bytes)

        assert len(rows) == 1
        assert rows[0]["username"] == "user1"

    def test_euckr_fallback(self):
        csv_bytes = (
            "username,nickname,role,group\n"
            "user1,김민준,,\n"
        ).encode("euc-kr")

        rows = parse_csv(csv_bytes)

        assert len(rows) == 1
        assert rows[0]["nickname"] == "김민준"

    def test_missing_required_columns_raises(self):
        csv_bytes = b"username,role\nkim,teacher\n"

        with pytest.raises(
            ValueError, match="nickname"
        ):
            parse_csv(csv_bytes)

    def test_empty_csv_raises(self):
        csv_bytes = b"username,nickname,role,group\n"

        with pytest.raises(ValueError, match="비어"):
            parse_csv(csv_bytes)

    def test_over_100_rows_raises(self):
        header = "username,nickname,role,group\n"
        rows = "".join(
            f"user_{i},닉{i},,\n" for i in range(101)
        )
        csv_bytes = (header + rows).encode("utf-8")

        with pytest.raises(ValueError, match="100"):
            parse_csv(csv_bytes)

    def test_over_1mb_raises(self):
        header = "username,nickname,role,group\n"
        big_row = f"user1,{'x' * (1024 * 1024)},,\n"
        csv_bytes = (header + big_row).encode("utf-8")

        with pytest.raises(ValueError, match="1MB"):
            parse_csv(csv_bytes)

    def test_strips_whitespace(self):
        csv_bytes = (
            "username,nickname,role,group\n"
            " kim , 김민준 , teacher , 1학년 \n"
        ).encode("utf-8")

        rows = parse_csv(csv_bytes)

        assert rows[0]["username"] == "kim"
        assert rows[0]["nickname"] == "김민준"
        assert rows[0]["role"] == "teacher"
        assert rows[0]["group"] == "1학년"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bulk_user_parse_csv.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_csv'`

- [ ] **Step 3: Write minimal implementation**

Create `src/services/admin_user_bulk.py`:

```python
"""Bulk user upload service — CSV parsing, validation, registration."""

import csv
import io
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.user import (
    BulkFailure,
    BulkPreviewResponse,
    BulkPreviewRow,
    BulkRegisterResponse,
    BulkUserEntry,
)
from src.models.user import User
from src.models.user_group import UserGroup

MAX_FILE_SIZE = 1024 * 1024  # 1MB
MAX_ROWS = 100
DEFAULT_PASSWORD = "00000000"
REQUIRED_COLUMNS = {"username", "nickname"}
ALL_COLUMNS = ["username", "nickname", "role", "group"]
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")


def parse_csv(file_content: bytes) -> list[dict]:
    """Parse CSV bytes into list of row dicts.

    Tries UTF-8 first, falls back to EUC-KR.
    Validates file size, required columns, and row count.

    Returns:
        List of dicts with keys: username, nickname, role, group
    """
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(
            "파일 크기가 1MB를 초과합니다."
        )

    text = None
    for encoding in ("utf-8-sig", "utf-8", "euc-kr"):
        try:
            text = file_content.decode(encoding)
            break
        except (UnicodeDecodeError, ValueError):
            continue

    if text is None:
        raise ValueError(
            "파일 인코딩을 인식할 수 없습니다. "
            "UTF-8 또는 EUC-KR을 사용해주세요."
        )

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV 헤더를 읽을 수 없습니다.")

    cleaned_fields = [
        f.strip().lower() for f in reader.fieldnames
    ]
    missing = REQUIRED_COLUMNS - set(cleaned_fields)
    if missing:
        raise ValueError(
            f"필수 컬럼이 누락되었습니다: "
            f"{', '.join(sorted(missing))}"
        )

    rows = []
    for raw_row in reader:
        row = {}
        for orig_key, clean_key in zip(
            reader.fieldnames, cleaned_fields
        ):
            val = (raw_row.get(orig_key) or "").strip()
            row[clean_key] = val
        rows.append({
            "username": row.get("username", ""),
            "nickname": row.get("nickname", ""),
            "role": row.get("role", ""),
            "group": row.get("group", ""),
        })

    if len(rows) == 0:
        raise ValueError("CSV 파일이 비어 있습니다.")

    if len(rows) > MAX_ROWS:
        raise ValueError(
            f"최대 {MAX_ROWS}명까지 업로드할 수 있습니다. "
            f"현재 {len(rows)}명"
        )

    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bulk_user_parse_csv.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/admin_user_bulk.py tests/unit/test_bulk_user_parse_csv.py
git commit -m "feat: add CSV parsing for bulk user upload"
```

---

### Task 3: Service — Validation (`validate_bulk_users`)

**Files:**
- Modify: `src/services/admin_user_bulk.py`
- Test: `tests/unit/test_bulk_user_validate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_bulk_user_validate.py`:

```python
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
        {
            "username": "kim_01",
            "nickname": "김민준",
            "role": "teacher",
            "group": "1학년",
        },
        {
            "username": "lee_02",
            "nickname": "이소연",
            "role": "",
            "group": "",
        },
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
async def test_duplicate_username_in_db(
    db_session: AsyncSession,
):
    existing = User(
        username="existing_user",
        nickname="기존",
        role="teacher",
    )
    existing.set_password("test1234")
    db_session.add(existing)
    await db_session.flush()

    rows = [
        {
            "username": "existing_user",
            "nickname": "중복",
            "role": "",
            "group": "",
        }
    ]

    result = await validate_bulk_users(rows, db_session)

    assert result.summary["error"] == 1
    assert "이미 존재하는 사용자 ID" in result.rows[0].errors


@pytest.mark.asyncio
async def test_duplicate_username_within_csv(
    db_session: AsyncSession,
):
    rows = [
        {
            "username": "dup_user",
            "nickname": "첫번째",
            "role": "",
            "group": "",
        },
        {
            "username": "dup_user",
            "nickname": "두번째",
            "role": "",
            "group": "",
        },
    ]

    result = await validate_bulk_users(rows, db_session)

    assert result.rows[0].errors == []
    assert "CSV 내 중복된 사용자 ID" in result.rows[1].errors


@pytest.mark.asyncio
async def test_invalid_username_format(
    db_session: AsyncSession,
):
    rows = [
        {
            "username": "ab",
            "nickname": "짧은",
            "role": "",
            "group": "",
        },
        {
            "username": "bad user!",
            "nickname": "특수문자",
            "role": "",
            "group": "",
        },
    ]

    result = await validate_bulk_users(rows, db_session)

    assert any(
        "3자" in e for e in result.rows[0].errors
    )
    assert any(
        "영문" in e for e in result.rows[1].errors
    )


@pytest.mark.asyncio
async def test_invalid_nickname(db_session: AsyncSession):
    rows = [
        {
            "username": "user_01",
            "nickname": "가",
            "role": "",
            "group": "",
        },
    ]

    result = await validate_bulk_users(rows, db_session)

    assert any(
        "2자" in e for e in result.rows[0].errors
    )


@pytest.mark.asyncio
async def test_invalid_role(db_session: AsyncSession):
    rows = [
        {
            "username": "user_01",
            "nickname": "닉네임",
            "role": "superadmin",
            "group": "",
        }
    ]

    result = await validate_bulk_users(rows, db_session)

    assert any(
        "유효하지 않은 역할" in e
        for e in result.rows[0].errors
    )


@pytest.mark.asyncio
async def test_invalid_group_name(
    db_session: AsyncSession,
):
    rows = [
        {
            "username": "user_01",
            "nickname": "닉네임",
            "role": "",
            "group": "존재하지않는그룹",
        }
    ]

    result = await validate_bulk_users(rows, db_session)

    assert any(
        "존재하지 않는 그룹" in e
        for e in result.rows[0].errors
    )


@pytest.mark.asyncio
async def test_groups_list_returned(
    db_session: AsyncSession,
):
    g1 = UserGroup(name="A그룹")
    g2 = UserGroup(name="B그룹")
    db_session.add_all([g1, g2])
    await db_session.flush()

    rows = [
        {
            "username": "user_01",
            "nickname": "닉네임",
            "role": "",
            "group": "",
        }
    ]

    result = await validate_bulk_users(rows, db_session)

    group_names = {g["name"] for g in result.groups}
    assert "A그룹" in group_names
    assert "B그룹" in group_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bulk_user_validate.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_bulk_users'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/services/admin_user_bulk.py`:

```python


async def validate_bulk_users(
    rows: list[dict],
    db: AsyncSession,
) -> BulkPreviewResponse:
    """Validate parsed CSV rows against DB state.

    Checks username format/length, nickname length,
    role validity, group existence, and duplicates.
    """
    # Load all existing usernames
    result = await db.execute(select(User.username))
    existing_usernames = {
        r[0] for r in result.all()
    }

    # Load all groups
    result = await db.execute(
        select(UserGroup).order_by(UserGroup.name)
    )
    all_groups = result.scalars().all()
    group_map = {g.name: g for g in all_groups}
    groups_list = [
        {"id": g.id, "name": g.name} for g in all_groups
    ]

    preview_rows = []
    seen_usernames: set[str] = set()
    valid_count = 0
    error_count = 0

    for i, row in enumerate(rows, start=1):
        errors: list[str] = []
        username = row.get("username", "")
        nickname = row.get("nickname", "")
        role = row.get("role", "").strip()
        group_name = row.get("group", "").strip()

        # Default role
        if not role:
            role = "teacher"

        # Validate username
        if len(username) < 3 or len(username) > 50:
            errors.append(
                "사용자 ID는 3자 이상 50자 이하여야 합니다."
            )
        elif not USERNAME_PATTERN.match(username):
            errors.append(
                "사용자 ID는 영문, 숫자, "
                "언더스코어만 사용 가능합니다."
            )

        # Validate nickname
        if len(nickname) < 2 or len(nickname) > 30:
            errors.append(
                "닉네임은 2자 이상 30자 이하여야 합니다."
            )

        # Validate role
        if role not in ("teacher", "admin"):
            errors.append(
                f"유효하지 않은 역할: {role}"
            )

        # Check DB duplicate
        if username in existing_usernames:
            errors.append("이미 존재하는 사용자 ID")

        # Check CSV-internal duplicate
        if username in seen_usernames:
            errors.append("CSV 내 중복된 사용자 ID")

        seen_usernames.add(username)

        # Validate group
        group_id = None
        resolved_group_name = None
        if group_name:
            group = group_map.get(group_name)
            if group:
                group_id = group.id
                resolved_group_name = group.name
            else:
                errors.append(
                    f"존재하지 않는 그룹: {group_name}"
                )
                resolved_group_name = group_name

        if errors:
            error_count += 1
        else:
            valid_count += 1

        preview_rows.append(
            BulkPreviewRow(
                row_num=i,
                username=username,
                nickname=nickname,
                role=role,
                group_name=resolved_group_name,
                group_id=group_id,
                errors=errors,
            )
        )

    return BulkPreviewResponse(
        rows=preview_rows,
        groups=groups_list,
        summary={
            "total": len(rows),
            "valid": valid_count,
            "error": error_count,
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bulk_user_validate.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/admin_user_bulk.py tests/unit/test_bulk_user_validate.py
git commit -m "feat: add bulk user validation with group/duplicate checking"
```

---

### Task 4: Service — Registration (`register_bulk_users`)

**Files:**
- Modify: `src/services/admin_user_bulk.py`
- Test: `tests/unit/test_bulk_user_register.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_bulk_user_register.py`:

```python
"""Unit tests for bulk user registration."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.user import BulkUserEntry
from src.models.user import User
from src.models.user_group import UserGroup
from src.services.admin_user_bulk import register_bulk_users


@pytest.mark.asyncio
async def test_register_creates_users(
    db_session: AsyncSession,
):
    group = UserGroup(name="TestGroup")
    db_session.add(group)
    await db_session.flush()

    users = [
        BulkUserEntry(
            username="new_user_1",
            nickname="새유저1",
            role="teacher",
            group_id=group.id,
        ),
        BulkUserEntry(
            username="new_user_2",
            nickname="새유저2",
            role="admin",
            group_id=None,
        ),
    ]

    result = await register_bulk_users(users, db_session)

    assert result.success_count == 2
    assert result.fail_count == 0
    assert result.failures == []

    created = (
        await db_session.execute(
            select(User).where(
                User.username.in_(
                    ["new_user_1", "new_user_2"]
                )
            )
        )
    ).scalars().all()
    created_map = {u.username: u for u in created}

    assert created_map["new_user_1"].nickname == "새유저1"
    assert created_map["new_user_1"].group_id == group.id
    assert created_map["new_user_1"].verify_password(
        "00000000"
    )
    assert created_map["new_user_2"].role == "admin"
    assert created_map["new_user_2"].group_id is None


@pytest.mark.asyncio
async def test_register_skips_duplicate_username(
    db_session: AsyncSession,
):
    existing = User(
        username="taken_user",
        nickname="기존유저",
        role="teacher",
    )
    existing.set_password("test1234")
    db_session.add(existing)
    await db_session.flush()

    users = [
        BulkUserEntry(
            username="taken_user",
            nickname="중복시도",
        ),
        BulkUserEntry(
            username="fresh_user",
            nickname="새유저",
        ),
    ]

    result = await register_bulk_users(users, db_session)

    assert result.success_count == 1
    assert result.fail_count == 1
    assert result.failures[0].username == "taken_user"
    assert "이미 존재" in result.failures[0].reason


@pytest.mark.asyncio
async def test_register_empty_list(
    db_session: AsyncSession,
):
    result = await register_bulk_users([], db_session)

    assert result.success_count == 0
    assert result.fail_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bulk_user_register.py -v`
Expected: FAIL — `ImportError: cannot import name 'register_bulk_users'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/services/admin_user_bulk.py`:

```python


async def register_bulk_users(
    users: list[BulkUserEntry],
    db: AsyncSession,
) -> BulkRegisterResponse:
    """Register validated users into the database.

    Processes each user individually — one failure
    does not affect others. Re-checks username
    uniqueness at registration time.
    """
    if not users:
        return BulkRegisterResponse(
            success_count=0,
            fail_count=0,
            failures=[],
        )

    # Re-check existing usernames at registration time
    usernames = [u.username for u in users]
    result = await db.execute(
        select(User.username).where(
            User.username.in_(usernames)
        )
    )
    existing = {r[0] for r in result.all()}

    success_count = 0
    failures: list[BulkFailure] = []

    for entry in users:
        if entry.username in existing:
            failures.append(
                BulkFailure(
                    username=entry.username,
                    nickname=entry.nickname,
                    reason="이미 존재하는 사용자 ID",
                )
            )
            continue

        new_user = User(
            username=entry.username,
            nickname=entry.nickname,
            role=entry.role,
            group_id=entry.group_id,
        )
        new_user.set_password(DEFAULT_PASSWORD)
        db.add(new_user)

        try:
            await db.flush()
            existing.add(entry.username)
            success_count += 1
        except Exception:
            await db.rollback()
            failures.append(
                BulkFailure(
                    username=entry.username,
                    nickname=entry.nickname,
                    reason="사용자 등록 중 오류가 발생했습니다.",
                )
            )

    return BulkRegisterResponse(
        success_count=success_count,
        fail_count=len(failures),
        failures=failures,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bulk_user_register.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/admin_user_bulk.py tests/unit/test_bulk_user_register.py
git commit -m "feat: add bulk user registration with per-row error handling"
```

---

### Task 5: Route — CSV Template Download

**Files:**
- Modify: `src/api/routes/admin_users.py`
- Test: `tests/contract/test_bulk_template_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/contract/test_bulk_template_endpoint.py`:

```python
"""Contract tests for bulk CSV template download."""

import pytest

from src.models.user import User


async def _login(client, username, password="test1234"):
    await client.post(
        "/login",
        data={"username": username, "password": password},
    )


@pytest.fixture
async def admin(async_session):
    user = User(
        username="tmpl_admin",
        nickname="관리자",
        role="admin",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def teacher(async_session):
    user = User(
        username="tmpl_teacher",
        nickname="교사",
        role="teacher",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


class TestBulkTemplateDownload:
    @pytest.mark.asyncio
    async def test_admin_can_download(
        self, async_client, admin
    ):
        await _login(async_client, admin.username)

        resp = await async_client.get(
            "/admin/users/bulk/template"
        )

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers[
            "content-disposition"
        ]
        content = resp.content.decode("utf-8-sig")
        assert "username" in content
        assert "nickname" in content

    @pytest.mark.asyncio
    async def test_teacher_forbidden(
        self, async_client, teacher
    ):
        await _login(async_client, teacher.username)

        resp = await async_client.get(
            "/admin/users/bulk/template"
        )

        assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/contract/test_bulk_template_endpoint.py -v`
Expected: FAIL — 404 (route not found)

- [ ] **Step 3: Write minimal implementation**

Add imports at the top of `src/api/routes/admin_users.py` (after existing imports):

```python
from fastapi.responses import HTMLResponse, Response
from src.api.schemas import (
    AdminUserResponse,
    BulkPreviewResponse,
    BulkRegisterRequest,
    BulkRegisterResponse,
    UserCreate,
    UserUpdate,
)
```

Note: replace the existing `HTMLResponse` import — it moves into the combined import from `fastapi.responses`. Also replace the existing `src.api.schemas` import block with the expanded one above.

Add the template endpoint before the existing `@router.post("/admin/users", ...)`:

```python
@router.get("/admin/users/bulk/template")
async def download_bulk_template(
    user: User = Depends(get_admin_user),
):
    """GET /admin/users/bulk/template — CSV template."""
    csv_content = "\ufeffusername,nickname,role,group\n"
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; "
                "filename=bulk_users_template.csv"
            )
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/contract/test_bulk_template_endpoint.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/admin_users.py tests/contract/test_bulk_template_endpoint.py
git commit -m "feat: add CSV template download endpoint for bulk user upload"
```

---

### Task 6: Route — CSV Preview

**Files:**
- Modify: `src/api/routes/admin_users.py`
- Test: `tests/contract/test_bulk_preview_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/contract/test_bulk_preview_endpoint.py`:

```python
"""Contract tests for bulk user preview endpoint."""

import pytest

from src.models.user import User
from src.models.user_group import UserGroup


async def _login(client, username, password="test1234"):
    await client.post(
        "/login",
        data={"username": username, "password": password},
    )


@pytest.fixture
async def admin(async_session):
    user = User(
        username="prev_admin",
        nickname="관리자",
        role="admin",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def group(async_session):
    g = UserGroup(name="1학년")
    async_session.add(g)
    await async_session.flush()
    return g


def _csv_file(content: str):
    return {
        "file": (
            "test.csv",
            content.encode("utf-8"),
            "text/csv",
        )
    }


class TestBulkPreview:
    @pytest.mark.asyncio
    async def test_valid_csv_returns_preview(
        self, async_client, admin, group
    ):
        await _login(async_client, admin.username)

        resp = await async_client.post(
            "/admin/users/bulk/preview",
            files=_csv_file(
                "username,nickname,role,group\n"
                "user_01,유저1,teacher,1학년\n"
                "user_02,유저2,,\n"
            ),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == 2
        assert data["summary"]["valid"] == 2
        assert data["rows"][0]["group_id"] == group.id
        assert len(data["groups"]) >= 1

    @pytest.mark.asyncio
    async def test_invalid_csv_returns_400(
        self, async_client, admin
    ):
        await _login(async_client, admin.username)

        resp = await async_client.post(
            "/admin/users/bulk/preview",
            files=_csv_file("username,role\nkim,teacher\n"),
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_username_shown_in_preview(
        self, async_client, async_session, admin
    ):
        existing = User(
            username="dup_user",
            nickname="기존",
            role="teacher",
        )
        existing.set_password("test1234")
        async_session.add(existing)
        await async_session.flush()

        await _login(async_client, admin.username)

        resp = await async_client.post(
            "/admin/users/bulk/preview",
            files=_csv_file(
                "username,nickname,role,group\n"
                "dup_user,중복시도,,\n"
            ),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["error"] == 1
        assert "이미 존재" in data["rows"][0]["errors"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/contract/test_bulk_preview_endpoint.py -v`
Expected: FAIL — 404 or 405 (route not found)

- [ ] **Step 3: Write minimal implementation**

Add import to the top of `src/api/routes/admin_users.py`:

```python
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
```

Note: add `File` and `UploadFile` to the existing `fastapi` import block.

Add the endpoint after the template endpoint:

```python
@router.post("/admin/users/bulk/preview")
async def preview_bulk_upload(
    file: UploadFile = File(...),
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/users/bulk/preview — Parse and validate CSV."""
    from src.services.admin_user_bulk import (
        parse_csv,
        validate_bulk_users,
    )

    content = await file.read()

    try:
        rows = parse_csv(content)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=str(e)
        )

    result = await validate_bulk_users(rows, db)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/contract/test_bulk_preview_endpoint.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/admin_users.py tests/contract/test_bulk_preview_endpoint.py
git commit -m "feat: add CSV preview endpoint with validation"
```

---

### Task 7: Route — Bulk Register

**Files:**
- Modify: `src/api/routes/admin_users.py`
- Test: `tests/contract/test_bulk_register_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/contract/test_bulk_register_endpoint.py`:

```python
"""Contract tests for bulk user registration endpoint."""

import pytest
from sqlalchemy import select

from src.models.user import User
from src.models.user_group import UserGroup


async def _login(client, username, password="test1234"):
    await client.post(
        "/login",
        data={"username": username, "password": password},
    )


@pytest.fixture
async def admin(async_session):
    user = User(
        username="reg_admin",
        nickname="관리자",
        role="admin",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def group(async_session):
    g = UserGroup(name="RegGroup")
    async_session.add(g)
    await async_session.flush()
    return g


class TestBulkRegister:
    @pytest.mark.asyncio
    async def test_register_creates_users(
        self, async_client, async_session, admin, group
    ):
        await _login(async_client, admin.username)

        resp = await async_client.post(
            "/admin/users/bulk/register",
            json={
                "users": [
                    {
                        "username": "bulk_r1",
                        "nickname": "벌크1",
                        "role": "teacher",
                        "group_id": group.id,
                    },
                    {
                        "username": "bulk_r2",
                        "nickname": "벌크2",
                        "role": "admin",
                        "group_id": None,
                    },
                ]
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success_count"] == 2
        assert data["fail_count"] == 0

        created = (
            await async_session.execute(
                select(User).where(
                    User.username.in_(
                        ["bulk_r1", "bulk_r2"]
                    )
                )
            )
        ).scalars().all()
        assert len(created) == 2

    @pytest.mark.asyncio
    async def test_register_reports_failures(
        self, async_client, async_session, admin
    ):
        existing = User(
            username="already_taken",
            nickname="기존",
            role="teacher",
        )
        existing.set_password("test1234")
        async_session.add(existing)
        await async_session.flush()

        await _login(async_client, admin.username)

        resp = await async_client.post(
            "/admin/users/bulk/register",
            json={
                "users": [
                    {
                        "username": "already_taken",
                        "nickname": "중복",
                    },
                    {
                        "username": "success_user",
                        "nickname": "성공",
                    },
                ]
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success_count"] == 1
        assert data["fail_count"] == 1
        assert (
            data["failures"][0]["username"]
            == "already_taken"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/contract/test_bulk_register_endpoint.py -v`
Expected: FAIL — 404 or 405 (route not found)

- [ ] **Step 3: Write minimal implementation**

Add the endpoint to `src/api/routes/admin_users.py` after the preview endpoint:

```python
@router.post("/admin/users/bulk/register")
async def register_bulk_users_endpoint(
    data: BulkRegisterRequest,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/users/bulk/register — Create users."""
    from src.services.admin_user_bulk import (
        register_bulk_users,
    )

    result = await register_bulk_users(data.users, db)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/contract/test_bulk_register_endpoint.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/admin_users.py tests/contract/test_bulk_register_endpoint.py
git commit -m "feat: add bulk user registration endpoint"
```

---

### Task 8: Template — Bulk Upload UI

**Files:**
- Modify: `src/templates/admin/users.html`

This task adds the three-step bulk upload modal to the users page. No automated test — this is a UI template change verified by visual inspection.

- [ ] **Step 1: Add header buttons**

In `src/templates/admin/users.html`, replace the header section (lines 7-15):

```html
  <header class="page-header-admin">
    <div class="header-content">
      <h1>사용자 관리</h1>
      <p class="subtitle">사용자 생성, 수정 및 삭제</p>
    </div>
    <div class="header-actions" style="display:flex;gap:8px;">
      <a href="/admin/users/bulk/template" class="btn btn-secondary" download>
        CSV 양식 다운로드
      </a>
      <button type="button" class="btn btn-primary" id="open-bulk-modal">
        일괄 추가
      </button>
      <button type="button" class="btn btn-primary" id="open-create-modal">
        + 새 사용자
      </button>
    </div>
  </header>
```

- [ ] **Step 2: Add bulk upload modal HTML**

Insert before `<!-- CREATE USER MODAL -->` (before line 83):

```html
<!-- BULK UPLOAD MODAL -->
<div class="modal-overlay" id="bulk-modal">
  <div class="modal-container" style="max-width:900px;width:95%;">
    <div class="modal-header">
      <h2 id="bulk-modal-title">일괄 사용자 추가</h2>
      <button type="button" class="close-modal-btn" onclick="closeBulkModal()">&times;</button>
    </div>
    <div class="modal-body" id="bulk-modal-body">
      <!-- Step 1: Upload -->
      <div id="bulk-step-upload">
        <div style="border:2px dashed var(--border-color,#4b5563);border-radius:12px;padding:40px 20px;text-align:center;">
          <p style="font-size:1.1rem;margin-bottom:8px;">CSV 파일을 선택하세요</p>
          <p style="color:var(--text-muted,#9ca3af);font-size:0.85rem;margin-bottom:16px;">양식: username, nickname, role(선택), group(선택)</p>
          <input type="file" id="bulk-file-input" accept=".csv" style="display:none;" />
          <button type="button" class="btn btn-primary" onclick="document.getElementById('bulk-file-input').click()">파일 선택</button>
          <p id="bulk-file-name" style="margin-top:12px;color:var(--text-muted,#9ca3af);font-size:0.85rem;"></p>
        </div>
        <p style="color:var(--text-muted,#9ca3af);font-size:0.8rem;margin-top:12px;text-align:center;">* 기본 비밀번호: 00000000</p>
        <p id="bulk-upload-error" style="color:#ef4444;text-align:center;margin-top:8px;display:none;"></p>
      </div>

      <!-- Step 2: Preview -->
      <div id="bulk-step-preview" style="display:none;">
        <div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;padding:12px;background:var(--bg-secondary,#1e293b);border-radius:8px;">
          <span style="color:var(--text-muted,#9ca3af);font-size:0.85rem;white-space:nowrap;">일괄 지정:</span>
          <select id="bulk-assign-role" class="filter-select" style="min-width:100px;">
            <option value="">역할 선택...</option>
            <option value="teacher">교사</option>
            <option value="admin">관리자</option>
          </select>
          <select id="bulk-assign-group" class="filter-select" style="min-width:140px;">
            <option value="">그룹 선택...</option>
          </select>
          <button type="button" class="btn btn-sm btn-primary" onclick="applyBulkAssign()">적용</button>
        </div>
        <div class="table-container" style="max-height:400px;overflow-y:auto;">
          <table class="data-table" id="bulk-preview-table">
            <thead>
              <tr>
                <th>#</th>
                <th>사용자 ID</th>
                <th>닉네임</th>
                <th>역할</th>
                <th>그룹</th>
                <th>상태</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody id="bulk-preview-body"></tbody>
          </table>
        </div>
        <button type="button" class="btn btn-sm btn-secondary" onclick="addBulkRow()" style="margin-top:8px;width:100%;border-style:dashed;">+ 사용자 추가</button>
      </div>

      <!-- Step 3: Result -->
      <div id="bulk-step-result" style="display:none;">
        <div style="display:flex;gap:16px;margin-bottom:20px;">
          <div style="flex:1;background:rgba(34,197,94,0.1);border:1px solid #166534;border-radius:8px;padding:16px;text-align:center;">
            <div id="bulk-success-count" style="font-size:1.8rem;font-weight:bold;color:#22c55e;">0</div>
            <div style="font-size:0.85rem;color:#86efac;">성공</div>
          </div>
          <div style="flex:1;background:rgba(239,68,68,0.1);border:1px solid #991b1b;border-radius:8px;padding:16px;text-align:center;">
            <div id="bulk-fail-count" style="font-size:1.8rem;font-weight:bold;color:#ef4444;">0</div>
            <div style="font-size:0.85rem;color:#fca5a5;">실패</div>
          </div>
        </div>
        <div id="bulk-failure-list" style="display:none;">
          <h4 style="color:#fca5a5;font-size:0.85rem;margin-bottom:8px;">실패 목록</h4>
          <table class="data-table">
            <thead>
              <tr><th>사용자 ID</th><th>닉네임</th><th>실패 사유</th></tr>
            </thead>
            <tbody id="bulk-failure-body"></tbody>
          </table>
        </div>
      </div>
    </div>
    <div class="modal-footer" id="bulk-modal-footer">
      <div id="bulk-summary" style="font-size:0.85rem;"></div>
      <div style="display:flex;gap:8px;">
        <button type="button" class="btn btn-secondary" onclick="closeBulkModal()">취소</button>
        <button type="button" class="btn btn-primary" id="bulk-register-btn" style="display:none;" onclick="submitBulkRegister()">등록</button>
        <button type="button" class="btn btn-primary" id="bulk-close-btn" style="display:none;" onclick="closeBulkModal();window.location.reload();">닫기</button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add bulk upload JavaScript**

Insert before the closing `</script>` tag (before line 362 — before `{% endblock %}`). Add inside the existing `<script>` block:

```javascript
  // ===== BULK UPLOAD =====
  let bulkPreviewData = [];
  let bulkGroups = [];

  document.getElementById('open-bulk-modal').addEventListener('click', () => {
    resetBulkModal();
    openModal('bulk-modal');
  });

  document.getElementById('bulk-file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    document.getElementById('bulk-file-name').textContent = file.name;
    document.getElementById('bulk-upload-error').style.display = 'none';

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/admin/users/bulk/preview', {
        method: 'POST',
        headers: { 'x-csrf-token': getCsrfToken() },
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        const errEl = document.getElementById('bulk-upload-error');
        errEl.textContent = err.detail || '파일 처리 중 오류가 발생했습니다.';
        errEl.style.display = 'block';
        return;
      }
      const data = await res.json();
      bulkPreviewData = data.rows;
      bulkGroups = data.groups;
      showBulkPreview();
    } catch (err) {
      const errEl = document.getElementById('bulk-upload-error');
      errEl.textContent = '서버 연결에 실패했습니다.';
      errEl.style.display = 'block';
    }
  });

  function resetBulkModal() {
    bulkPreviewData = [];
    bulkGroups = [];
    document.getElementById('bulk-file-input').value = '';
    document.getElementById('bulk-file-name').textContent = '';
    document.getElementById('bulk-upload-error').style.display = 'none';
    document.getElementById('bulk-step-upload').style.display = '';
    document.getElementById('bulk-step-preview').style.display = 'none';
    document.getElementById('bulk-step-result').style.display = 'none';
    document.getElementById('bulk-register-btn').style.display = 'none';
    document.getElementById('bulk-close-btn').style.display = 'none';
    document.getElementById('bulk-summary').innerHTML = '';
    document.getElementById('bulk-modal-title').textContent = '일괄 사용자 추가';
  }

  function closeBulkModal() {
    closeModal('bulk-modal');
  }

  function groupOptions(selectedId) {
    let html = '<option value="">그룹 없음</option>';
    bulkGroups.forEach(g => {
      const sel = g.id === selectedId ? ' selected' : '';
      html += `<option value="${g.id}"${sel}>${g.name}</option>`;
    });
    return html;
  }

  function showBulkPreview() {
    document.getElementById('bulk-step-upload').style.display = 'none';
    document.getElementById('bulk-step-preview').style.display = '';
    document.getElementById('bulk-register-btn').style.display = '';
    document.getElementById('bulk-modal-title').textContent = '일괄 사용자 추가 — 미리보기';

    // Populate group dropdown for bulk assign
    const assignGroup = document.getElementById('bulk-assign-group');
    assignGroup.innerHTML = '<option value="">그룹 선택...</option>';
    bulkGroups.forEach(g => {
      assignGroup.innerHTML += `<option value="${g.id}">${g.name}</option>`;
    });

    renderPreviewTable();
  }

  function renderPreviewTable() {
    const tbody = document.getElementById('bulk-preview-body');
    tbody.innerHTML = '';

    let validCount = 0, errorCount = 0;
    bulkPreviewData.forEach((row, idx) => {
      const hasErr = row.errors && row.errors.length > 0;
      if (hasErr) errorCount++; else validCount++;

      const tr = document.createElement('tr');
      if (hasErr) tr.style.background = 'rgba(239,68,68,0.1)';
      tr.innerHTML = `
        <td>${idx + 1}</td>
        <td><input type="text" value="${row.username}" class="bulk-input" data-idx="${idx}" data-field="username" style="width:120px;"></td>
        <td><input type="text" value="${row.nickname}" class="bulk-input" data-idx="${idx}" data-field="nickname" style="width:100px;"></td>
        <td>
          <select class="filter-select bulk-select" data-idx="${idx}" data-field="role">
            <option value="teacher"${row.role==='teacher'?' selected':''}>교사</option>
            <option value="admin"${row.role==='admin'?' selected':''}>관리자</option>
          </select>
        </td>
        <td>
          <select class="filter-select bulk-select" data-idx="${idx}" data-field="group_id">
            ${groupOptions(row.group_id)}
          </select>
        </td>
        <td>${hasErr
          ? '<span style="color:#ef4444;font-size:0.8rem;">⚠ ' + row.errors.join(', ') + '</span>'
          : '<span style="color:#22c55e;font-size:0.8rem;">✓ 정상</span>'
        }</td>
        <td><button type="button" class="btn btn-sm btn-danger" onclick="removeBulkRow(${idx})">✕</button></td>
      `;
      tbody.appendChild(tr);
    });

    // Update summary
    document.getElementById('bulk-summary').innerHTML =
      `<span style="color:#22c55e;">정상 ${validCount}명</span> | ` +
      `<span style="color:#ef4444;">에러 ${errorCount}명</span> | ` +
      `<span>총 ${bulkPreviewData.length}명</span>`;
    document.getElementById('bulk-register-btn').textContent = `등록 (${validCount}명)`;

    // Bind input change events
    tbody.querySelectorAll('.bulk-input, .bulk-select').forEach(el => {
      el.addEventListener('change', (e) => {
        const idx = parseInt(e.target.dataset.idx);
        const field = e.target.dataset.field;
        if (field === 'group_id') {
          const val = e.target.value;
          bulkPreviewData[idx].group_id = val ? parseInt(val) : null;
          const grp = bulkGroups.find(g => g.id === parseInt(val));
          bulkPreviewData[idx].group_name = grp ? grp.name : null;
        } else {
          bulkPreviewData[idx][field] = e.target.value;
        }
        // Clear errors on edit (user is fixing them)
        bulkPreviewData[idx].errors = [];
        renderPreviewTable();
      });
    });
  }

  function removeBulkRow(idx) {
    bulkPreviewData.splice(idx, 1);
    renderPreviewTable();
  }

  function addBulkRow() {
    bulkPreviewData.push({
      row_num: bulkPreviewData.length + 1,
      username: '',
      nickname: '',
      role: 'teacher',
      group_name: null,
      group_id: null,
      errors: [],
    });
    renderPreviewTable();
  }

  function applyBulkAssign() {
    const role = document.getElementById('bulk-assign-role').value;
    const groupId = document.getElementById('bulk-assign-group').value;

    bulkPreviewData.forEach(row => {
      if (role) row.role = role;
      if (groupId) {
        row.group_id = parseInt(groupId);
        const grp = bulkGroups.find(g => g.id === parseInt(groupId));
        row.group_name = grp ? grp.name : null;
      }
    });
    renderPreviewTable();
  }

  async function submitBulkRegister() {
    const validUsers = bulkPreviewData
      .filter(r => !r.errors || r.errors.length === 0)
      .filter(r => r.username && r.nickname)
      .map(r => ({
        username: r.username,
        nickname: r.nickname,
        role: r.role || 'teacher',
        group_id: r.group_id || null,
      }));

    if (validUsers.length === 0) {
      alert('등록할 유효한 사용자가 없습니다.');
      return;
    }

    document.getElementById('bulk-register-btn').disabled = true;

    try {
      const res = await fetch('/admin/users/bulk/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csrf-token': getCsrfToken(),
        },
        body: JSON.stringify({ users: validUsers }),
      });

      const data = await res.json();
      showBulkResult(data);
    } catch (err) {
      alert('등록 중 오류가 발생했습니다.');
      document.getElementById('bulk-register-btn').disabled = false;
    }
  }

  function showBulkResult(data) {
    document.getElementById('bulk-step-preview').style.display = 'none';
    document.getElementById('bulk-step-result').style.display = '';
    document.getElementById('bulk-register-btn').style.display = 'none';
    document.getElementById('bulk-close-btn').style.display = '';
    document.getElementById('bulk-summary').innerHTML = '';
    document.getElementById('bulk-modal-title').textContent = '일괄 사용자 추가 — 결과';

    document.getElementById('bulk-success-count').textContent = data.success_count;
    document.getElementById('bulk-fail-count').textContent = data.fail_count;

    if (data.failures && data.failures.length > 0) {
      document.getElementById('bulk-failure-list').style.display = '';
      const tbody = document.getElementById('bulk-failure-body');
      tbody.innerHTML = '';
      data.failures.forEach(f => {
        tbody.innerHTML += `<tr style="background:rgba(239,68,68,0.1);">
          <td>${f.username}</td><td>${f.nickname}</td>
          <td style="color:#fca5a5;">${f.reason}</td>
        </tr>`;
      });
    }
  }
```

- [ ] **Step 4: Verify the app starts and serves the page**

Run: `cd /mnt/d/dev/misconcept_platform && python -c "from src.main import app; print('App loads OK')"`
Expected: `App loads OK`

- [ ] **Step 5: Commit**

```bash
git add src/templates/admin/users.html
git commit -m "feat: add bulk user upload modal UI with preview and results"
```

---

### Task 9: Integration Verification

Run the full test suite to ensure nothing is broken.

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run all contract tests**

Run: `pytest tests/contract/ -v`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS, no import errors, no failures

- [ ] **Step 4: Final commit if any fixups were needed**

If any tests failed and were fixed:

```bash
git add -A
git commit -m "fix: resolve test issues from bulk user upload integration"
```
