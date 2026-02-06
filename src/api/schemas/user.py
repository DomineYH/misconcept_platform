"""User Pydantic schemas for admin API."""
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=50
    )
    password: str = Field(
        ..., min_length=4, max_length=128
    )
    nickname: str = Field(
        ..., min_length=2, max_length=30
    )
    role: str = Field(default="teacher")
    group_id: int | None = None


class UserUpdate(BaseModel):
    nickname: str | None = Field(
        None, min_length=2, max_length=30
    )
    role: str | None = None
    group_id: int | None = None
    password: str | None = Field(
        None, min_length=4, max_length=128
    )


class AdminUserResponse(BaseModel):
    id: int
    username: str
    nickname: str
    role: str
    group_id: int | None = None
    group_name: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
