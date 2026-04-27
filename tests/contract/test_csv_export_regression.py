"""Contract tests: CSV export regression snapshots.

Ensures export output is byte-stable across code changes and
that summary.feedback is always plain text (not JSON).

Run `pytest tests/contract/ --update-snapshots` to regenerate
snapshot files on first run or after intentional format changes.
"""

import csv
import hashlib
import io
import os

import pytest

SNAP_DIR = os.path.join(os.path.dirname(__file__), "snapshots")


async def _seed_deterministic_session(
    async_db_session, test_scenario, test_teacher
):
    """Create a session with fixed timestamps for deterministic CSV."""
    from datetime import datetime, timezone

    from src.models.message import Message
    from src.models.question_analysis import QuestionAnalysis
    from src.models.session import Session
    from src.models.session_summary import SessionSummary

    started = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    ended = datetime(2026, 1, 15, 10, 5, 12, tzinfo=timezone.utc)

    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=test_teacher.id,
        started_at=started,
        ended_at=ended,
        tutor_intervention_count=2,
    )
    async_db_session.add(session)
    await async_db_session.flush()

    msgs = [
        Message(
            session_id=session.id,
            role="teacher",
            content="How did you solve it?",
            created_at=datetime(2026, 1, 15, 10, 1, 0, tzinfo=timezone.utc),
        ),
        Message(
            session_id=session.id,
            role="student",
            content="I added the numerators.",
            created_at=datetime(2026, 1, 15, 10, 1, 30, tzinfo=timezone.utc),
        ),
        Message(
            session_id=session.id,
            role="tutor",
            content="Try asking about the denominator.",
            created_at=datetime(2026, 1, 15, 10, 2, 0, tzinfo=timezone.utc),
        ),
    ]
    async_db_session.add_all(msgs)
    await async_db_session.flush()

    qa = QuestionAnalysis(
        message_id=msgs[0].id,
        label="Pressing",
        confidence=0.9,
        meta_json='{"summary":"Good pressing question."}',
    )
    async_db_session.add(qa)
    await async_db_session.flush()

    summary = SessionSummary(
        session_id=session.id,
        feedback="학생 풀이 과정을 물어본 것은 좋은 " "출발이었어요!",
        distribution='{"Pressing":1,"Linking":0,' '"Directing":0,"Recall":0}',
        created_at=datetime(2026, 1, 15, 10, 5, 12, tzinfo=timezone.utc),
    )
    async_db_session.add(summary)
    await async_db_session.flush()

    return session


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _snapshot_path(name: str) -> str:
    return os.path.join(SNAP_DIR, name)


def _load_snapshot(name: str) -> str:
    path = _snapshot_path(name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read().strip()


def _save_snapshot(name: str, value: str):
    os.makedirs(SNAP_DIR, exist_ok=True)
    path = _snapshot_path(name)
    with open(path, "w") as f:
        f.write(value + "\n")


@pytest.mark.anyio
async def test_user_csv_export_stable(
    async_db_session,
    test_scenario,
    test_teacher,
):
    """User CSV export must be byte-stable vs snapshot."""
    from src.services.export import CSVExporter

    session = await _seed_deterministic_session(
        async_db_session, test_scenario, test_teacher
    )
    exporter = CSVExporter()
    csv_str = await exporter.export_session(session.id, async_db_session)
    h = _sha256(csv_str)
    snap = _load_snapshot("csv_user_export.sha256")
    if snap is None:
        _save_snapshot("csv_user_export.sha256", h)
        pytest.skip("Snapshot created on first run")
    assert h == snap, (
        f"CSV hash mismatch: got {h}, expected {snap}. "
        "Run with --update-snapshots if intentional."
    )


@pytest.mark.anyio
async def test_admin_csv_export_stable(
    async_db_session,
    test_scenario,
    test_teacher,
):
    """Admin CSV export must be byte-stable vs snapshot."""
    from src.services.export import CSVExporter

    session = await _seed_deterministic_session(
        async_db_session, test_scenario, test_teacher
    )
    exporter = CSVExporter()
    csv_str = await exporter.export_session_admin(session.id, async_db_session)
    h = _sha256(csv_str)
    snap = _load_snapshot("csv_admin_export.sha256")
    if snap is None:
        _save_snapshot("csv_admin_export.sha256", h)
        pytest.skip("Snapshot created on first run")
    assert h == snap, f"Admin CSV hash mismatch: got {h}, expected {snap}."


@pytest.mark.anyio
async def test_bulk_csv_export_stable(
    async_db_session,
    test_scenario,
    test_teacher,
):
    """Bulk CSV export must be byte-stable vs snapshot."""
    from src.services.export import CSVExporter

    session = await _seed_deterministic_session(
        async_db_session, test_scenario, test_teacher
    )
    exporter = CSVExporter()
    csv_str = await exporter.export_multiple_sessions(
        [session.id], async_db_session
    )
    h = _sha256(csv_str)
    snap = _load_snapshot("csv_bulk_export.sha256")
    if snap is None:
        _save_snapshot("csv_bulk_export.sha256", h)
        pytest.skip("Snapshot created on first run")
    assert h == snap, f"Bulk CSV hash mismatch: got {h}, expected {snap}."


@pytest.mark.anyio
async def test_feedback_cell_is_plain_text(
    async_db_session,
    test_scenario,
    test_teacher,
):
    """summary.feedback cell must NOT start with { or [."""
    from src.services.export import CSVExporter

    session = await _seed_deterministic_session(
        async_db_session, test_scenario, test_teacher
    )
    exporter = CSVExporter()
    csv_str = await exporter.export_session(session.id, async_db_session)
    reader = csv.DictReader(io.StringIO(csv_str))
    for row in reader:
        if row["role"] == "summary":
            fb = row["feedback"]
            assert not fb.startswith(
                "{"
            ), f"Feedback looks like JSON dict: {fb[:60]}"
            assert not fb.startswith(
                "["
            ), f"Feedback looks like JSON list: {fb[:60]}"
            return
    pytest.fail("No summary row found in CSV export")
