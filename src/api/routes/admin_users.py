"""Admin user management routes."""
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_admin_user, get_db_session, templates
from src.api.schemas import (
    AdminUserResponse,
    UserCreate,
    UserUpdate,
)
from src.models.session import Session
from src.models.user import User
from src.models.user_group import UserGroup

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin Users"])


@router.get("/admin/users", response_class=HTMLResponse)
async def list_users(
    request: Request,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/users - User management page."""

    result = await db.execute(
        select(User).order_by(User.id.desc())
    )
    users = result.scalars().all()

    groups_result = await db.execute(
        select(UserGroup).order_by(UserGroup.name)
    )
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
            detail="사용자 ID는 영문, 숫자, "
            "언더스코어만 사용 가능합니다.",
        )

    # Check unique username
    existing = await db.execute(
        select(User).where(
            User.username == data.username
        )
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
    await db.commit()
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


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """PUT /admin/users/{id} - Update user."""

    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    if data.nickname is not None:
        target.nickname = data.nickname
    if data.role is not None:
        if data.role not in (
            "teacher", "admin"
        ):
            raise HTTPException(
                status_code=400,
                detail="유효하지 않은 역할입니다.",
            )
        target.role = data.role
    if data.group_id is not None:
        if data.group_id == 0:
            target.group_id = None
        else:
            group = await db.get(
                UserGroup, data.group_id
            )
            if not group:
                raise HTTPException(
                    status_code=400,
                    detail="그룹을 찾을 수 없습니다.",
                )
            target.group_id = data.group_id
    if data.password is not None:
        target.set_password(data.password)

    await db.commit()
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


@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """DELETE /admin/users/{id} - Delete user."""

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

    # Check for sessions
    session_count = await db.scalar(
        select(func.count(Session.id)).where(
            Session.teacher_id == user_id
        )
    )

    await db.delete(target)
    await db.commit()

    return {
        "status": "deleted",
        "user_id": user_id,
        "had_sessions": (session_count or 0) > 0,
    }
