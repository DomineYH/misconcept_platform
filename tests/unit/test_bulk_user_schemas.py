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
            rows=[BulkPreviewRow(row_num=1, username="a", nickname="가")],
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
        entry = BulkUserEntry(username="u2", nickname="닉2", role="admin", group_id=5)
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
            failures=[BulkFailure(username="dup", nickname="중복", reason="이미 존재하는 사용자 ID")],
        )
        assert resp.success_count == 2
        assert resp.failures[0].reason == "이미 존재하는 사용자 ID"
