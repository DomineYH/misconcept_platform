"""Integration test for CSV export workflow (T054)."""

import csv
import io
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.scenario_group import ScenarioGroup
from src.models.user import User
from src.models.user_group import UserGroup


@pytest.fixture(autouse=True)
async def seed_csv_test_data(db_session: AsyncSession):
    """Seed test data for CSV export tests."""
    # Create group for teachers
    group = UserGroup(name="CSV Test Group")
    db_session.add(group)
    await db_session.flush()

    # Create all users referenced in tests
    usernames = [
        "teacher_csv_001",
        "sensitive_student_123",
        "teacher_ts_001",
        "teacher_roles_001",
        "teacher_labels_001",
        "teacher_summary_001",
    ]
    for uname in usernames:
        user = User(
            username=uname,
            nickname=f"닉_{uname}",
            role="teacher",
            group_id=group.id,
        )
        user.set_password("test1234")
        db_session.add(user)

    # Create framework
    framework = AnalysisFramework(
        name="CSV Export Framework",
        description="Framework for CSV export tests",
        labels_json=(
            '["high_leverage",' ' "medium_leverage",' ' "low_leverage"]'
        ),
    )
    db_session.add(framework)
    await db_session.flush()

    # Create template
    template = PromptTemplate(
        bot_type="student",
        template_name="CSV Student Template",
        version=1,
        template_text="You are a test student bot.",
    )
    db_session.add(template)
    await db_session.flush()

    # Create scenario (id=1 since first in DB)
    scenario = Scenario(
        title="CSV Test Scenario",
        prompt="Test prompt for CSV export",
        student_profile="Test student profile",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()

    # Link scenario to group
    sg = ScenarioGroup(scenario_id=scenario.id, group_id=group.id)
    db_session.add(sg)
    await db_session.commit()


class TestCSVExportWorkflow:
    """Test complete CSV export workflow (T054)."""

    def test_csv_export_format_and_content(self, test_client: TestClient):
        """
        Verify CSV export format and content.

        Workflow:
        1. Create session with messages
        2. End session to trigger analysis
        3. Export CSV
        4. Verify CSV format, headers, timestamps
        """
        # Step 1: Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_csv_001",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
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
                data={"content": content},
                cookies=cookies,
            )

        # Step 2: End session and analyze
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )

        # Step 3: Export CSV
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv",
            cookies=cookies,
        )
        assert export_response.status_code == 200

        # Step 4: Verify CSV format
        csv_content = export_response.text

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Verify we have rows
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
            assert col in csv_reader.fieldnames, f"Missing column: {col}"

        # Verify session_id is consistent
        for row in rows:
            assert row["session_id"] == str(session_id)

        # Verify scenario_title is populated
        assert len(rows[0]["scenario_title"]) > 0

    def test_csv_anonymization(self, test_client: TestClient):
        """Verify CSV export anonymizes username."""
        # Login with specific username
        username = "sensitive_student_123"
        login_response = test_client.post(
            "/login",
            data={
                "username": username,
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        # Create session and send message
        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Test message"},
            cookies=cookies,
        )

        # End, analyze, and export
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv",
            cookies=cookies,
        )

        csv_content = export_response.text

        # Verify raw username is NOT in CSV
        assert username not in csv_content

        # Verify student_hash is present (SHA-256 hex)
        hash_pattern = re.compile(r"[a-f0-9]{64}")
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        assert len(rows) > 0
        assert hash_pattern.match(rows[0]["student_hash"])

    def test_csv_timestamp_format(self, test_client: TestClient):
        """Verify CSV timestamps are ISO 8601."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_ts_001",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Send message
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Timestamp test"},
            cookies=cookies,
        )

        # End, analyze, and export
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv",
            cookies=cookies,
        )

        csv_content = export_response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Verify ISO 8601 timestamp format
        timestamp_pattern = re.compile(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
        )

        for row in rows:
            if row["timestamp"]:
                assert timestamp_pattern.match(row["timestamp"]), (
                    f"Invalid timestamp:" f" {row['timestamp']}"
                )

    def test_csv_includes_all_roles(self, test_client: TestClient):
        """Verify CSV includes teacher and student messages."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_roles_001",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Send message
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Is this correct?"},
            cookies=cookies,
        )

        # End, analyze, and export
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv",
            cookies=cookies,
        )

        csv_content = export_response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Collect unique roles
        roles = {row["role"] for row in rows if row["role"]}

        # Should have at least teacher and student
        assert "teacher" in roles
        assert "student" in roles

    def test_csv_includes_question_labels(self, test_client: TestClient):
        """Verify CSV has question analysis labels."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_labels_001",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Send teacher message
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "What causes rain?"},
            cookies=cookies,
        )

        # End session and analyze
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )

        # Export CSV
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv",
            cookies=cookies,
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
        # Confidence should be between 0 and 1
        confidence = float(teacher_row["confidence"])
        assert 0.0 <= confidence <= 1.0

    def test_csv_includes_session_summary_row(self, test_client: TestClient):
        """Verify CSV includes session summary row."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_summary_001",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Send messages
        for content in [
            "Question 1",
            "Question 2",
            "Question 3",
        ]:
            test_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": content},
                cookies=cookies,
            )

        # End, analyze, and export
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        export_response = test_client.get(
            f"/sessions/{session_id}/export.csv",
            cookies=cookies,
        )

        csv_content = export_response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Find summary row
        summary_rows = [
            row
            for row in rows
            if row["role"] == "summary"
            or "SUMMARY" in row.get("content", "").upper()
        ]

        # Should have at least one summary row
        assert len(summary_rows) > 0

        # Summary row should have feedback
        summary_row = summary_rows[0]
        assert len(summary_row.get("feedback", "")) > 0
