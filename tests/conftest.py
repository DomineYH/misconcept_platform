"""Pytest configuration and shared fixtures."""
import asyncio
import pytest
from typing import AsyncGenerator

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.db.connection import Base
from src.main import app
from src.api.dependencies import get_db_session


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with schema."""
    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, future=True
    )
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
def test_client(db_session: AsyncSession) -> TestClient:
    """Create FastAPI test client with test database."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
