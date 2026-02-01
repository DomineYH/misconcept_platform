"""Integration test for CSV export workflow (T054)."""
import csv
import io
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.user import User
from src.models.session import Session


class TestCSVExportWorkflow:
    """Test complete CSV export workflow (T054)."""

    def test_csv_export_format_and_content(
        self, test_client: TestClient
    ):
        """
        Verify CSV export format, anonymization, and timestamp formatting.

        Workflow:
        1. Create session with messages
        2. End session to trigger analysis
        3. Export CSV
        4. Verify CSV format, headers, anonymization, timestamps
        """
        # Step 1: Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_csv_001", "nickname": "CSV테스트"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send messages
        teacher_messages = [
            "What is the water cycle?",
            "Can you explain evaporation?",
            "Is condensation part of it?",
        ]

        for content in teacher_messages:
            test_client.post(
                f"/sessions/{session_id}/messages",
                json={"content": content},
                cookies=cookies,
            )

        # Step 2: End session and analyze
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)
        test_client.post(f"/sessions/{session_id}/analyze", cookies=cookies)

        # Step 3: Export CSV
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )
        assert export_response.status_code == 200

        # Step 4: Verify CSV format
        csv_content = export_response.text

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Verify we have rows (at least teacher messages)
        assert len(rows) >= 3

        # Verify required columns
        required_columns = [
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
        for col in required_columns:
            assert (
                col in csv_reader.fieldnames
            ), f"Missing column: {col}"

        # Verify session_id is consistent
        for row in rows:
            assert row["session_id"] == str(session_id)

        # Verify scenario_title is populated
        assert len(rows[0]["scenario_title"]) > 0

    def test_csv_anonymization(self, test_client: TestClient):
        """Verify CSV export anonymizes student_uid."""
        # Login with specific student_uid
        student_uid = "sensitive_student_123"
        login_response = test_client.post(
            "/login",
            data={"student_uid": student_uid, "nickname": "익명화테스트"},
        )
        cookies = login_response.cookies

        # Create session and send message
        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Test message"},
            cookies=cookies,
        )

        # End, analyze, and export
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)
        test_client.post(f"/sessions/{session_id}/analyze", cookies=cookies)
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        csv_content = export_response.text

        # Verify raw student_uid is NOT in CSV
        assert student_uid not in csv_content

        # Verify student_hash is present (SHA-256 = 64 hex chars)
        hash_pattern = re.compile(r"[a-f0-9]{64}")
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        assert len(rows) > 0
        assert hash_pattern.match(rows[0]["student_hash"])

    def test_csv_timestamp_format(self, test_client: TestClient):
        """Verify CSV timestamps are ISO 8601 formatted."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_ts_001", "nickname": "타임스탬프"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send message
        test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Timestamp test"},
            cookies=cookies,
        )

        # End, analyze, and export
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)
        test_client.post(f"/sessions/{session_id}/analyze", cookies=cookies)
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        csv_content = export_response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Verify ISO 8601 timestamp format (YYYY-MM-DD HH:MM:SS or T)
        timestamp_pattern = re.compile(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
        )

        for row in rows:
            if row["timestamp"]:  # Skip empty timestamps
                assert timestamp_pattern.match(
                    row["timestamp"]
                ), f"Invalid timestamp: {row['timestamp']}"

    def test_csv_includes_all_roles(self, test_client: TestClient):
        """Verify CSV includes teacher, student, and tutor messages."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_roles_001", "nickname": "역할테스트"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send message (will trigger student and possibly tutor responses)
        test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "Is this correct?"},  # Low-leverage
            cookies=cookies,
        )

        # End, analyze, and export
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)
        test_client.post(f"/sessions/{session_id}/analyze", cookies=cookies)
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        csv_content = export_response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Collect unique roles
        roles = {row["role"] for row in rows if row["role"]}

        # Should have at least teacher and student
        assert "teacher" in roles
        assert "student" in roles
        # Tutor may or may not appear depending on intervention

    def test_csv_includes_question_labels(self, test_client: TestClient):
        """Verify CSV includes question analysis labels for teacher msgs."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "teacher_labels_001", "nickname": "라벨테스트"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send teacher message
        test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": "What causes rain?"},
            cookies=cookies,
        )

        # End session and analyze
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)
        test_client.post(f"/sessions/{session_id}/analyze", cookies=cookies)

        # Export CSV
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        csv_content = export_response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Find teacher message row
        teacher_rows = [row for row in rows if row["role"] == "teacher"]
        assert len(teacher_rows) > 0

        # Teacher message should have label
        teacher_row = teacher_rows[0]
        assert teacher_row["label"] in [
            "high_leverage",
            "medium_leverage",
            "low_leverage",
        ]
        # Confidence should be a number between 0 and 1
        confidence = float(teacher_row["confidence"])
        assert 0.0 <= confidence <= 1.0

    def test_csv_includes_session_summary_row(
        self, test_client: TestClient
    ):
        """Verify CSV includes session summary row at the end."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "student_uid": "teacher_summary_001",
                "nickname": "요약테스트",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send messages
        for content in ["Question 1", "Question 2", "Question 3"]:
            test_client.post(
                f"/sessions/{session_id}/messages",
                json={"content": content},
                cookies=cookies,
            )

        # End, analyze, and export
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)
        test_client.post(f"/sessions/{session_id}/analyze", cookies=cookies)
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        csv_content = export_response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Find summary row (role = "summary" or content contains "SUMMARY")
        summary_rows = [
            row
            for row in rows
            if row["role"] == "summary"
            or "SUMMARY" in row.get("content", "").upper()
        ]

        # Should have at least one summary row
        assert len(summary_rows) > 0

        # Summary row should have feedback populated
        summary_row = summary_rows[0]
        assert len(summary_row.get("feedback", "")) > 0
