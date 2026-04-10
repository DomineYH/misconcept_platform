"""Admin user management routes."""

import csv
import io
import logging
import re

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_admin_user, get_db_session, templates
from src.api.schemas import (
    AdminUserResponse,
    BulkPreviewResponse,
    BulkRegisterRequest,
    BulkRegisterResponse,
    UserCreate,
    UserUpdate,
)
from src.models.session import Session
from src.models.user import User
from src.models.user_group import UserGroup

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin Users"])

PATTERN_USERNAME_RE = re.compile(
    r"^(?P<prefix>[A-Za-z0-9_]+)_(?P<number>\d+)$"
)
CSV_TEMPLATE_HEADERS = [
    "username",
    "nickname",
    "password",
    "role",
    "group_name",
]
MAX_BULK_CSV_BYTES = 1024 * 1024
MAX_BULK_CSV_ROWS = 1000
MAX_FAILURE_SAMPLES = 20


def _validate_bulk_username(username: str) -> None:
    """Validate bulk username format."""
    if not username.replace("_", "").isalnum():
        raise ValueError(
            "사용자 ID는 영문, 숫자, 언더스코어만 사용 가능합니다."
        )


def _validate_bulk_role(role: str) -> None:
    """Validate supported bulk role."""
    if role not in ("teacher", "admin"):
        raise ValueError("유효하지 않은 역할입니다.")


def _validate_bulk_password(password: str) -> None:
    """Validate bulk password rules without changing legacy schema."""
    if not (4 <= len(password) <= 128):
        raise ValueError("비밀번호는 4자 이상 128자 이하여야 합니다.")


async def _validate_bulk_group_id(
    db: AsyncSession,
    group_id: int | None,
) -> None:
    """Validate optional bulk group id."""
    if group_id is None:
        return

    group = await db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(
            status_code=400,
            detail="그룹을 찾을 수 없습니다.",
        )


async def _load_group_name_map(
    db: AsyncSession,
) -> dict[str, UserGroup]:
    """Load groups by name for CSV imports."""
    result = await db.execute(select(UserGroup).order_by(UserGroup.name))
    groups = result.scalars().all()
    return {group.name: group for group in groups}


def _build_bulk_summary(
    created_usernames: list[str],
    errors: list[dict[str, int | str | None]],
) -> dict[str, object]:
    """Match the shared bulk summary response contract."""
    return {
        "created_count": len(created_usernames),
        "failed_count": len(errors),
        "created_usernames": created_usernames,
        "errors": errors[:MAX_FAILURE_SAMPLES],
    }


async def _create_pattern_users(
    db: AsyncSession,
    start_username: str,
    count: int,
    role: str,
    group_id: int | None,
) -> dict[str, object]:
    """Create users from prefix_number pattern."""
    match = PATTERN_USERNAME_RE.fullmatch(start_username)
    if not match:
        raise HTTPException(
            status_code=400,
            detail=(
                "시작 사용자 ID는 prefix_number 형식이어야 합니다. "
                "예: teacher_001"
            ),
        )

    try:
        _validate_bulk_role(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _validate_bulk_group_id(db, group_id)

    prefix = match.group("prefix")
    current = int(match.group("number"))
    width = len(match.group("number"))

    created_usernames: list[str] = []
    skipped_existing_count = 0

    while len(created_usernames) < count:
        username = f"{prefix}_{current:0{width}d}"
        existing = await db.execute(
            select(User).where(User.username == username)
        )
        if existing.scalar_one_or_none():
            skipped_existing_count += 1
            current += 1
            continue

        user = User(
            username=username,
            nickname=username,
            role=role,
            group_id=group_id,
        )
        user.set_password("0000")
        db.add(user)
        await db.flush()
        created_usernames.append(user.username)
        current += 1

    summary = _build_bulk_summary(created_usernames, [])
    summary["skipped_existing_count"] = skipped_existing_count
    return summary


async def _parse_bulk_pattern_request(
    request: Request,
) -> tuple[str, int, str, int | None]:
    """Accept JSON or form payloads for bulk pattern creation."""
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    start_username = str(
        payload.get("start_username") or payload.get("username") or ""
    ).strip()
    role = str(payload.get("role") or "teacher").strip()

    try:
        count = int(payload.get("count"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="count는 1 이상 1000 이하의 정수여야 합니다.",
        ) from exc

    if not start_username:
        raise HTTPException(
            status_code=400,
            detail="start_username 값이 필요합니다.",
        )
    if count < 1 or count > 1000:
        raise HTTPException(
            status_code=400,
            detail="count는 1 이상 1000 이하의 정수여야 합니다.",
        )

    group_id_raw = payload.get("group_id")
    if group_id_raw in ("", None, "null"):
        group_id = None
    else:
        try:
            group_id = int(group_id_raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail="group_id는 정수여야 합니다.",
            ) from exc

    return start_username, count, role, group_id


async def _create_users_from_csv(
    db: AsyncSession,
    upload: UploadFile,
) -> dict[str, object]:
    """Create users from uploaded CSV."""
    raw = await upload.read(MAX_BULK_CSV_BYTES + 1)
    if len(raw) > MAX_BULK_CSV_BYTES:
        raise HTTPException(
            status_code=400,
            detail="CSV 파일은 1 MiB 이하여야 합니다.",
        )

    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="CSV 파일은 UTF-8 인코딩이어야 합니다.",
        ) from exc

    reader = csv.DictReader(io.StringIO(decoded))
    if reader.fieldnames != CSV_TEMPLATE_HEADERS:
        raise HTTPException(
            status_code=400,
            detail=(
                "CSV 헤더는 정확히 "
                "username,nickname,password,role,group_name 이어야 합니다."
            ),
        )

    rows = [
        row
        for row in reader
        if any((value or "").strip() for value in row.values())
    ]
    if len(rows) > MAX_BULK_CSV_ROWS:
        raise HTTPException(
            status_code=400,
            detail="CSV 데이터 행은 최대 1000개까지 업로드할 수 있습니다.",
        )

    group_map = await _load_group_name_map(db)
    created_usernames: list[str] = []
    failures: list[dict[str, int | str | None]] = []

    for row_number, row in enumerate(rows, start=2):
        username = (row.get("username") or "").strip()
        nickname = (row.get("nickname") or "").strip()
        password = row.get("password") or ""
        role = (row.get("role") or "").strip()
        group_name = (row.get("group_name") or "").strip()

        try:
            if not username:
                raise ValueError("username 값이 비어 있습니다.")
            if not nickname:
                raise ValueError("nickname 값이 비어 있습니다.")

            _validate_bulk_username(username)
            _validate_bulk_password(password)
            _validate_bulk_role(role)

            group_id = None
            if group_name:
                group = group_map.get(group_name)
                if not group:
                    raise ValueError("존재하지 않는 group_name 입니다.")
                group_id = group.id

            existing = await db.execute(
                select(User).where(User.username == username)
            )
            if existing.scalar_one_or_none():
                raise ValueError("이미 존재하는 사용자 ID입니다.")

            user = User(
                username=username,
                nickname=nickname,
                role=role,
                group_id=group_id,
            )
            user.set_password(password)
            db.add(user)
            await db.flush()
            created_usernames.append(user.username)
        except ValueError as exc:
            if len(failures) < MAX_FAILURE_SAMPLES:
                failures.append(
                    {
                        "row": row_number,
                        "username": username or None,
                        "message": str(exc),
                    }
                )

    return _build_bulk_summary(created_usernames, failures)


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


@router.post(
    "/admin/users/bulk/preview",
    response_model=BulkPreviewResponse,
)
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


@router.post(
    "/admin/users/bulk/register",
    response_model=BulkRegisterResponse,
)
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


@router.get("/admin/users", response_class=HTMLResponse)
async def list_users(
    request: Request,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/users - User management page."""

    result = await db.execute(select(User).order_by(User.id.desc()))
    users = result.scalars().all()

    groups_result = await db.execute(select(UserGroup).order_by(UserGroup.name))
    groups = groups_result.scalars().all()

    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "groups": groups,
        },
    )


@router.post("/admin/users", status_code=201)
async def create_user(
    data: UserCreate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/users - Create new user."""

    # Validate username format
    if not data.username.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="사용자 ID는 영문, 숫자, " "언더스코어만 사용 가능합니다.",
        )

    # Check unique username
    existing = await db.execute(
        select(User).where(User.username == data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 사용자 ID입니다.",
        )

    # Verify group exists if provided
    if data.group_id is not None:
        group = await db.get(UserGroup, data.group_id)
        if not group:
            raise HTTPException(
                status_code=400,
                detail="그룹을 찾을 수 없습니다.",
            )

    # Validate role
    if data.role not in ("teacher", "admin"):
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 역할입니다.",
        )

    new_user = User(
        username=data.username,
        nickname=data.nickname,
        role=data.role,
        group_id=data.group_id,
    )
    new_user.set_password(data.password)

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    group_name = None
    if new_user.group_id:
        grp = await db.get(UserGroup, new_user.group_id)
        group_name = grp.name if grp else None

    return AdminUserResponse(
        id=new_user.id,
        username=new_user.username,
        nickname=new_user.nickname,
        role=new_user.role,
        group_id=new_user.group_id,
        group_name=group_name,
        created_at=new_user.created_at,
    )


@router.post("/admin/users/bulk-pattern")
async def create_users_bulk_pattern(
    request: Request,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/users/bulk-pattern - Bulk create users by pattern."""
    del user
    start_username, count, role, group_id = (
        await _parse_bulk_pattern_request(request)
    )
    return await _create_pattern_users(
        db=db,
        start_username=start_username,
        count=count,
        role=role,
        group_id=group_id,
    )


@router.get("/admin/users/bulk-template.csv")
async def download_users_bulk_template(
    user: User = Depends(get_admin_user),
):
    """GET /admin/users/bulk-template.csv - Download CSV template."""
    del user
    return Response(
        content="\ufeff" + ",".join(CSV_TEMPLATE_HEADERS) + "\n",
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; filename=admin_users_bulk_template.csv"
            )
        },
    )


@router.post("/admin/users/bulk-csv")
async def create_users_bulk_csv(
    file: UploadFile = File(...),
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/users/bulk-csv - Bulk create users from CSV upload."""
    del user
    return await _create_users_from_csv(db=db, upload=file)


@router.post("/admin/users/{user_id}/update")
async def update_user(
    user_id: int,
    data: UserUpdate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/users/{id}/update - Update user."""

    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    if data.nickname is not None:
        target.nickname = data.nickname
    if data.role is not None:
        if data.role not in ("teacher", "admin"):
            raise HTTPException(
                status_code=400,
                detail="유효하지 않은 역할입니다.",
            )
        target.role = data.role
    if data.group_id is not None:
        if data.group_id == 0:
            target.group_id = None
        else:
            group = await db.get(UserGroup, data.group_id)
            if not group:
                raise HTTPException(
                    status_code=400,
                    detail="그룹을 찾을 수 없습니다.",
                )
            target.group_id = data.group_id
    if data.password is not None:
        target.set_password(data.password)

    await db.flush()
    await db.refresh(target)

    group_name = None
    if target.group_id:
        grp = await db.get(UserGroup, target.group_id)
        group_name = grp.name if grp else None

    return AdminUserResponse(
        id=target.id,
        username=target.username,
        nickname=target.nickname,
        role=target.role,
        group_id=target.group_id,
        group_name=group_name,
        created_at=target.created_at,
    )


@router.post("/admin/users/{user_id}/delete")
async def delete_user(
    user_id: int,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/users/{id}/delete - Delete user."""

    if user_id == user.id:
        raise HTTPException(
            status_code=400,
            detail="자기 자신은 삭제할 수 없습니다.",
        )

    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    # Check for active sessions
    active_count = await db.scalar(
        select(func.count(Session.id)).where(
            Session.teacher_id == user_id,
            Session.ended_at.is_(None),
            Session.deleted_at.is_(None),
        )
    )

    if active_count and active_count > 0:
        raise HTTPException(
            status_code=400,
            detail="활성 세션이 있는 사용자는 "
            "삭제할 수 없습니다. "
            "먼저 세션을 종료해주세요.",
        )

    # Nullify teacher_id on ended sessions
    await db.execute(
        update(Session)
        .where(Session.teacher_id == user_id)
        .values(teacher_id=None)
    )

    await db.delete(target)
    await db.flush()

    return {
        "status": "deleted",
        "user_id": user_id,
    }
