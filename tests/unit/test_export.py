"""
Unit tests for CSVExporter service (T065).

Tests CSV format, anonymization, and summary row inclusion.
"""

import csv
import io
import pytest
from datetime import datetime

from src.services.export import CSVExporter


def test_anonymize_student_deterministic():
    """Test student anonymization is deterministic with same salt."""
    exporter = CSVExporter()

    # Same inputs should produce same hash
    hash1 = exporter._anonymize_student("student123", "salt1")
    hash2 = exporter._anonymize_student("student123", "salt1")
    assert hash1 == hash2


def test_anonymize_student_different_salt():
    """Test different salts produce different hashes."""
    exporter = CSVExporter()

    hash1 = exporter._anonymize_student("student123", "salt1")
    hash2 = exporter._anonymize_student("student123", "salt2")
    assert hash1 != hash2


def test_anonymize_student_different_uid():
    """Test different student UIDs produce different hashes."""
    exporter = CSVExporter()

    hash1 = exporter._anonymize_student("student123", "salt1")
    hash2 = exporter._anonymize_student("student456", "salt1")
    assert hash1 != hash2


def test_anonymize_student_format():
    """Test anonymized hash is 64-character hexadecimal."""
    exporter = CSVExporter()

    student_hash = exporter._anonymize_student("student123", "salt1")
    assert len(student_hash) == 64
    assert all(c in "0123456789abcdef" for c in student_hash)


@pytest.mark.asyncio
async def test_export_session_csv_format(
    async_db_session, sample_session_with_messages
):
    """Test CSV export has correct format and headers."""
    exporter = CSVExporter()
    session = sample_session_with_messages

    # Export session
    csv_content = await exporter.export_session(session.id, async_db_session)

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    # Verify headers
    expected_headers = [
        "session_id",
        "scenario_title",
        "student_hash",
        "timestamp",
        "role",
        "content",
        "label",
        "confidence",
        "feedback",
    ]
    assert reader.fieldnames == expected_headers

    # Verify at least one row
    assert len(rows) > 0


@pytest.mark.asyncio
async def test_export_session_anonymization(
    async_db_session, sample_session_with_messages
):
    """Test student identifier is anonymized in CSV."""
    exporter = CSVExporter()
    session = sample_session_with_messages

    # Export session
    csv_content = await exporter.export_session(session.id, async_db_session)

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    # Check student_hash is not original student_uid
    for row in rows:
        assert row["student_hash"] != session.teacher.student_uid
        assert len(row["student_hash"]) == 64


@pytest.mark.asyncio
async def test_export_session_with_analysis(
    async_db_session, sample_session_with_analysis
):
    """Test CSV includes question analysis labels and confidence."""
    exporter = CSVExporter()
    session = sample_session_with_analysis

    # Export session
    csv_content = await exporter.export_session(session.id, async_db_session)

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    # Find teacher message rows with analysis
    teacher_rows = [r for r in rows if r["role"] == "teacher"]
    assert len(teacher_rows) > 0

    # Verify analysis data present
    for row in teacher_rows:
        if row["label"]:
            assert row["label"] in [
                "Pressing",
                "Linking",
                "Directing",
                "Recall",
            ]
            if row["confidence"]:
                confidence = float(row["confidence"])
                assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_export_session_with_summary(
    async_db_session, sample_session_with_summary
):
    """Test CSV includes session summary row."""
    exporter = CSVExporter()
    session = sample_session_with_summary

    # Export session
    csv_content = await exporter.export_session(session.id, async_db_session)

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    # Find summary row
    summary_rows = [r for r in rows if r["role"] == "summary"]
    assert len(summary_rows) == 1

    # Verify summary content
    summary_row = summary_rows[0]
    assert summary_row["content"] == "Session Summary"
    assert len(summary_row["feedback"]) > 0


@pytest.mark.asyncio
async def test_export_session_timestamp_format(
    async_db_session, sample_session_with_messages
):
    """Test timestamps are in ISO format."""
    exporter = CSVExporter()
    session = sample_session_with_messages

    # Export session
    csv_content = await exporter.export_session(session.id, async_db_session)

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    # Verify all timestamps are valid ISO format
    for row in rows:
        # Should parse without error
        datetime.fromisoformat(row["timestamp"])


@pytest.mark.asyncio
async def test_export_session_not_found(async_db_session):
    """Test error when exporting nonexistent session."""
    exporter = CSVExporter()

    # Should raise ValueError
    with pytest.raises(ValueError, match="Session .* not found"):
        await exporter.export_session(99999, async_db_session)


@pytest.mark.asyncio
async def test_export_multiple_sessions(async_db_session, multiple_sessions):
    """Test exporting multiple sessions combines into one CSV."""
    exporter = CSVExporter()
    session_ids = [s.id for s in multiple_sessions]

    # Export multiple sessions
    csv_content = await exporter.export_multiple_sessions(
        session_ids, async_db_session
    )

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    # Should have rows from multiple sessions
    unique_sessions = set(r["session_id"] for r in rows)
    assert len(unique_sessions) == len(session_ids)


@pytest.mark.asyncio
async def test_export_multiple_sessions_single_header(
    async_db_session, multiple_sessions
):
    """Test multiple sessions export has single header."""
    exporter = CSVExporter()
    session_ids = [s.id for s in multiple_sessions]

    csv_content = await exporter.export_multiple_sessions(
        session_ids, async_db_session
    )

    lines = csv_content.strip().split("\n")
    header_count = sum(1 for line in lines if line.startswith("session_id,"))
    assert header_count == 1


class TestAdminExport:
    """Admin CSV export with teacher info and meta_json."""

    ADMIN_HEADERS = [
        "session_id",
        "scenario_id",
        "scenario_title",
        "teacher_id",
        "teacher_student_uid",
        "teacher_nickname",
        "session_started_at",
        "session_ended_at",
        "message_id",
        "message_created_at",
        "role",
        "content",
        "label",
        "confidence",
        "meta_json",
        "feedback",
    ]

    @pytest.mark.asyncio
    async def test_export_session_admin_headers(
        self, async_db_session, sample_session_with_messages
    ):
        """Verify admin export has all required columns."""
        exporter = CSVExporter()
        session = sample_session_with_messages

        csv_content = await exporter.export_session_admin(
            session.id, async_db_session
        )

        reader = csv.DictReader(io.StringIO(csv_content))
        assert list(reader.fieldnames) == self.ADMIN_HEADERS

    @pytest.mark.asyncio
    async def test_export_session_admin_teacher_info(
        self, async_db_session, sample_session_with_messages
    ):
        """Verify admin export includes raw teacher info (not hashed)."""
        exporter = CSVExporter()
        session = sample_session_with_messages

        csv_content = await exporter.export_session_admin(
            session.id, async_db_session
        )

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) > 0

        row = rows[0]
        assert row["teacher_student_uid"] == "teacher_001"
        assert row["teacher_nickname"] == "테스트교사"
        assert row["teacher_id"] == str(session.teacher_id)

    @pytest.mark.asyncio
    async def test_export_session_admin_meta_json(
        self, async_db_session, sample_session_with_analysis
    ):
        """Verify admin export includes meta_json for teacher messages."""
        exporter = CSVExporter()
        session = sample_session_with_analysis

        csv_content = await exporter.export_session_admin(
            session.id, async_db_session
        )

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        teacher_rows = [r for r in rows if r["role"] == "teacher"]
        assert len(teacher_rows) > 0

        assert teacher_rows[0]["meta_json"] != ""
        assert "summary" in teacher_rows[0]["meta_json"]

    @pytest.mark.asyncio
    async def test_export_multiple_sessions_admin(
        self, async_db_session, multiple_sessions
    ):
        """Verify admin bulk export works with multiple sessions."""
        exporter = CSVExporter()
        session_ids = [s.id for s in multiple_sessions]

        csv_content = await exporter.export_multiple_sessions_admin(
            session_ids, async_db_session
        )

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        unique_sessions = set(r["session_id"] for r in rows)
        assert len(unique_sessions) == len(session_ids)
