"""Unit tests for CSV parsing in bulk user service."""

import os

os.environ.setdefault("TESTING", "true")

import pytest  # noqa: E402

from src.services.admin_user_bulk import parse_csv  # noqa: E402


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
            "\ufeffusername,nickname,role,group\nuser1,닉네임1,,\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert len(rows) == 1
        assert rows[0]["username"] == "user1"

    def test_euckr_fallback(self):
        csv_bytes = ("username,nickname,role,group\nuser1,김민준,,\n").encode(
            "euc-kr"
        )
        rows = parse_csv(csv_bytes)
        assert len(rows) == 1
        assert rows[0]["nickname"] == "김민준"

    def test_missing_required_columns_raises(self):
        csv_bytes = b"username,role\nkim,teacher\n"
        with pytest.raises(ValueError, match="nickname"):
            parse_csv(csv_bytes)

    def test_empty_csv_raises(self):
        csv_bytes = b"username,nickname,role,group\n"
        with pytest.raises(ValueError, match="비어"):
            parse_csv(csv_bytes)

    def test_over_100_rows_raises(self):
        header = "username,nickname,role,group\n"
        rows = "".join(f"user_{i},닉{i},,\n" for i in range(101))
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
            "username,nickname,role,group\n kim , 김민준 , teacher , 1학년 \n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert rows[0]["username"] == "kim"
        assert rows[0]["nickname"] == "김민준"
        assert rows[0]["role"] == "teacher"
        assert rows[0]["group"] == "1학년"

    def test_tab_delimiter(self):
        csv_bytes = (
            "username\tnickname\trole\tgroup\n" "user1\t닉1\t\t\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert len(rows) == 1
        assert rows[0]["username"] == "user1"
        assert rows[0]["nickname"] == "닉1"

    def test_semicolon_delimiter(self):
        csv_bytes = ("username;nickname;role;group\n" "user1;닉1;;\n").encode(
            "utf-8"
        )
        rows = parse_csv(csv_bytes)
        assert len(rows) == 1
        assert rows[0]["username"] == "user1"

    def test_double_bom(self):
        csv_bytes = (
            "\ufeff\ufeffusername,nickname,role,group\n" "user1,닉1,,\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert rows[0]["username"] == "user1"

    def test_korean_column_aliases(self):
        csv_bytes = ("사용자,닉네임,역할,그룹\n" "user1,닉1,,\n").encode(
            "utf-8"
        )
        rows = parse_csv(csv_bytes)
        assert rows[0]["username"] == "user1"
        assert rows[0]["nickname"] == "닉1"

    def test_error_message_shows_found_columns(self):
        csv_bytes = b"name,email\nkim,kim@test.com\n"
        with pytest.raises(ValueError, match=r"발견된 컬럼.*name.*email"):
            parse_csv(csv_bytes)
