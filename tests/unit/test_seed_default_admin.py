"""Unit tests for default admin account bootstrapping."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import config
from src.db.connection import Base
from src.db.seed import ensure_default_admin_user
from src.models.user import User
from src.models.user_group import UserGroup


@pytest.mark.asyncio
async def test_ensure_default_admin_user_creates_loginable_admin(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Create the default admin account when it is missing."""
    monkeypatch.setattr(config, "ADMIN_DEFAULT_PASSWORD", "admin123")

    admin_id = await ensure_default_admin_user(db_session)
    await db_session.flush()

    admin = (
        await db_session.execute(select(User).where(User.id == admin_id))
    ).scalar_one()
    group = (
        await db_session.execute(
            select(UserGroup).where(UserGroup.id == admin.group_id)
        )
    ).scalar_one()

    assert admin.username == "admin"
    assert admin.role == "admin"
    assert admin.verify_password("admin123")
    assert group.name == "default"


@pytest.mark.asyncio
async def test_ensure_default_admin_user_is_idempotent(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Repeated calls should not create duplicate admin users."""
    monkeypatch.setattr(config, "ADMIN_DEFAULT_PASSWORD", "admin123")

    first_admin_id = await ensure_default_admin_user(db_session)
    second_admin_id = await ensure_default_admin_user(db_session)
    await db_session.flush()

    admins = (
        (await db_session.execute(select(User).where(User.username == "admin")))
        .scalars()
        .all()
    )

    assert first_admin_id == second_admin_id
    assert len(admins) == 1


@pytest.mark.asyncio
async def test_ensure_default_admin_user_survives_concurrent_startup(
    monkeypatch: pytest.MonkeyPatch,
):
    """Two workers racing against a fresh DB must not crash on UNIQUE.

    Regression for the concurrent-startup race in
    ``src/db/seed.py:50-54`` / ``:89-107``. Before the fix, both
    workers saw the admin row missing, both attempted ``INSERT``, and
    the loser raised ``IntegrityError`` on ``user.username`` or
    ``user_group.name`` — aborting the FastAPI lifespan on boot.
    """
    monkeypatch.setattr(config, "ADMIN_DEFAULT_PASSWORD", "admin123")

    # File-backed SQLite so two independent engines share real state.
    # In-memory DBs are per-connection in aiosqlite and can't reproduce
    # the cross-worker race.
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "race.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        # One engine to own the schema; two more to act as independent
        # "workers" racing the bootstrap.
        schema_engine = create_async_engine(db_url, future=True)
        async with schema_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await schema_engine.dispose()

        worker_a_engine = create_async_engine(db_url, future=True)
        worker_b_engine = create_async_engine(db_url, future=True)
        try:
            session_a = async_sessionmaker(
                worker_a_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            session_b = async_sessionmaker(
                worker_b_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            async def bootstrap_with(session_factory) -> int:
                async with session_factory() as session:
                    admin_id = await ensure_default_admin_user(session)
                    await session.commit()
                    return admin_id

            # Run both workers concurrently. asyncio.gather interleaves
            # at await points, giving the SELECT-INSERT window that
            # triggered the race.
            id_a, id_b = await asyncio.gather(
                bootstrap_with(session_a),
                bootstrap_with(session_b),
            )

            # Same canonical admin row for both workers.
            assert id_a == id_b

            # Verify exactly one admin / one default group in the DB.
            verify_engine = create_async_engine(db_url, future=True)
            try:
                verify_session_factory = async_sessionmaker(
                    verify_engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )
                async with verify_session_factory() as session:
                    admin_count = (
                        await session.execute(
                            text(
                                "SELECT COUNT(*) FROM user "
                                "WHERE username = 'admin'"
                            )
                        )
                    ).scalar_one()
                    group_count = (
                        await session.execute(
                            text(
                                "SELECT COUNT(*) FROM user_group "
                                "WHERE name = 'default'"
                            )
                        )
                    ).scalar_one()
                    assert admin_count == 1
                    assert group_count == 1
            finally:
                await verify_engine.dispose()
        finally:
            await worker_a_engine.dispose()
            await worker_b_engine.dispose()


@pytest.mark.asyncio
async def test_ensure_default_admin_user_does_not_promote_existing_teacher(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A pre-existing non-admin 'admin' user must never be promoted.

    Regression for Codex P1: previously, if a teacher-role user named
    'admin' existed (created via the admin UI or a DB edit), calling
    ensure_default_admin_user() would silently rewrite role='admin'
    and reset password_hash to ADMIN_DEFAULT_PASSWORD — a privilege
    escalation vector exposed on every boot when
    BOOTSTRAP_ADMIN_ON_STARTUP=true.
    """
    monkeypatch.setattr(config, "ADMIN_DEFAULT_PASSWORD", "admin123")

    existing = User(
        username="admin",
        nickname="Pre-existing Teacher",
        role="teacher",
    )
    existing.set_password("original-secret")
    db_session.add(existing)
    await db_session.flush()
    original_hash = existing.password_hash
    original_id = existing.id

    returned_id = await ensure_default_admin_user(db_session)
    await db_session.flush()
    # Raw SQL UPDATE inside the seed path bypasses the ORM identity map,
    # so refresh to read the actual DB state (not the cached instance).
    await db_session.refresh(existing)

    assert returned_id == original_id
    assert existing.role == "teacher"
    assert existing.password_hash == original_hash
    assert existing.verify_password("original-secret")


@pytest.mark.asyncio
async def test_ensure_default_admin_reconciles_mismatched_password(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """An existing admin whose password differs from the configured
    default is reset so admin/<ADMIN_DEFAULT_PASSWORD> always logs in.

    This guarantees the documented bootstrap credentials keep working
    across branch switches even when the admin row was created earlier
    with a different password.
    """
    monkeypatch.setattr(config, "ADMIN_DEFAULT_PASSWORD", "admin123")

    admin = User(
        username="admin",
        nickname="Administrator",
        role="admin",
    )
    admin.set_password("some-other-password")
    db_session.add(admin)
    await db_session.flush()

    await ensure_default_admin_user(db_session)
    await db_session.flush()
    await db_session.refresh(admin)

    assert admin.role == "admin"
    assert admin.verify_password("admin123")
    assert not admin.verify_password("some-other-password")


@pytest.mark.asyncio
async def test_ensure_default_admin_user_preserves_mismatched_password_in_production(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Production bootstrap must not reset a rotated admin password."""
    monkeypatch.setattr(config, "ENV", "production")
    monkeypatch.setattr(config, "ADMIN_DEFAULT_PASSWORD", "admin123")

    admin = User(
        username="admin",
        nickname="Administrator",
        role="admin",
    )
    admin.set_password("rotated-password")
    db_session.add(admin)
    await db_session.flush()
    original_hash = admin.password_hash

    await ensure_default_admin_user(db_session)
    await db_session.flush()
    await db_session.refresh(admin)

    assert admin.role == "admin"
    assert admin.password_hash == original_hash
    assert admin.verify_password("rotated-password")
    assert not admin.verify_password("admin123")


@pytest.mark.asyncio
async def test_ensure_default_admin_user_recovers_empty_password(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Emptying an admin's password_hash triggers a reseed on next call.

    This is the documented lockout-recovery workflow: operator clears
    the hash in the DB, restarts with ADMIN_DEFAULT_PASSWORD set, and
    the next bootstrap regenerates the hash. Only allowed when the
    row is already role='admin'.
    """
    monkeypatch.setattr(config, "ADMIN_DEFAULT_PASSWORD", "recovered-pw")

    admin = User(
        username="admin",
        nickname="Locked Out Admin",
        role="admin",
        password_hash="",
    )
    db_session.add(admin)
    await db_session.flush()

    await ensure_default_admin_user(db_session)
    await db_session.flush()
    # Raw SQL UPDATE inside the seed path bypasses the ORM identity map.
    # Expire the cached instance so the next read hits the DB.
    await db_session.refresh(admin)

    assert admin.role == "admin"
    assert admin.password_hash != ""
    assert admin.verify_password("recovered-pw")
