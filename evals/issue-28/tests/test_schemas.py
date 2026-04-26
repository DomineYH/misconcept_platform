"""Tests for eval harness Pydantic schemas (E14)."""

import importlib
import json
import sys
from pathlib import Path

import pytest

# evals/issue-28 has a hyphen — not importable as a package.
# Add the directory to sys.path and import schemas directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
schemas = importlib.import_module("schemas")

DialogueMessage = schemas.DialogueMessage
ExpertLabel = schemas.ExpertLabel
GoldenSession = schemas.GoldenSession
RubricScore = schemas.RubricScore
Scorecard = schemas.Scorecard

EXAMPLE_PATH = Path(__file__).parent.parent / "golden_sessions.example.json"


class TestDialogueMessage:
    """Tests for DialogueMessage schema."""

    def test_valid_message(self):
        msg = DialogueMessage(role="teacher", content="Hello", id=1)
        assert msg.role == "teacher"
        assert msg.content == "Hello"
        assert msg.id == 1

    def test_all_roles(self):
        for role in ("teacher", "student", "tutor"):
            msg = DialogueMessage(role=role, content="Hi", id=1)
            assert msg.role == role


class TestGoldenSession:
    """Tests for GoldenSession schema."""

    def test_minimal_valid(self):
        gs = GoldenSession(
            session_id="test-001",
            scenario_title="Test",
            misconception="Test misconception",
            messages=[DialogueMessage(role="teacher", content="Q?", id=1)],
        )
        assert gs.session_id == "test-001"
        assert gs.expected_labels.strengths_ideal == []

    def test_with_expected_labels(self):
        gs = GoldenSession(
            session_id="test-002",
            scenario_title="분수 덧셈",
            misconception="분모 통분 불가",
            messages=[
                DialogueMessage(role="teacher", content="Q?", id=1),
                DialogueMessage(role="student", content="A", id=2),
            ],
            expected_labels={
                "strengths_ideal": [1],
                "improvements_ideal": [2],
                "dialogue_markers_ideal": [
                    {"message_id": 1, "marker": "good_moment"}
                ],
            },
        )
        assert gs.expected_labels.strengths_ideal == [1]
        assert gs.expected_labels.improvements_ideal == [2]
        assert len(gs.expected_labels.dialogue_markers_ideal) == 1

    def test_empty_messages_rejected(self):
        with pytest.raises(Exception):
            GoldenSession(
                session_id="test-003",
                scenario_title="X",
                misconception="X",
                messages=[],
            )

    def test_example_file_loads(self):
        """Golden sessions example file parses as list of GoldenSession."""
        with open(EXAMPLE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        sessions = [GoldenSession(**gs) for gs in raw]
        assert len(sessions) >= 3
        # First session should be the 분수 덧셈 example
        assert "분수" in sessions[0].misconception


class TestExpertLabel:
    """Tests for ExpertLabel schema."""

    def test_valid_label(self):
        label = ExpertLabel(
            session_id="test-001",
            alternative_question="왜 그렇게 생각했어?",
            score=4.0,
            notes="Good scaffolding",
        )
        assert label.score == 4.0

    def test_score_bounds(self):
        with pytest.raises(Exception):
            ExpertLabel(
                session_id="test",
                alternative_question="Q?",
                score=6.0,
            )
        with pytest.raises(Exception):
            ExpertLabel(
                session_id="test",
                alternative_question="Q?",
                score=-1.0,
            )


class TestRubricScore:
    """Tests for RubricScore schema."""

    def test_valid_score(self):
        rs = RubricScore(
            session_id="test-001",
            mathematical_correctness=4.0,
            pedagogical_soundness=3.5,
            tone=5.0,
            length=4.0,
            verbatim_integrity=5.0,
            message_id_validity=5.0,
        )
        assert rs.mean == pytest.approx((4.0 + 3.5 + 5.0 + 4.0 + 5.0 + 5.0) / 6)

    def test_mean_perfect_score(self):
        rs = RubricScore(
            session_id="test",
            mathematical_correctness=5.0,
            pedagogical_soundness=5.0,
            tone=5.0,
            length=5.0,
            verbatim_integrity=5.0,
            message_id_validity=5.0,
        )
        assert rs.mean == 5.0


class TestScorecard:
    """Tests for Scorecard schema and pass_gate."""

    def _make_scorecard(self, **overrides) -> Scorecard:
        defaults = dict(
            timestamp="2026-01-01T00:00:00Z",
            model="mock",
            prompt_hash="abc123",
            n_sessions=1,
            strengths_recall=0.80,
            strengths_precision=0.75,
            alt_question_mean_score=3.5,
            programmatic_pass=True,
        )
        defaults.update(overrides)
        return Scorecard(**defaults)

    def test_pass_gate_all_thresholds_met(self):
        sc = self._make_scorecard()
        assert sc.pass_gate is True

    def test_fail_low_recall(self):
        sc = self._make_scorecard(strengths_recall=0.60)
        assert sc.pass_gate is False

    def test_fail_low_precision(self):
        sc = self._make_scorecard(strengths_precision=0.60)
        assert sc.pass_gate is False

    def test_fail_low_alt_question(self):
        sc = self._make_scorecard(alt_question_mean_score=2.5)
        assert sc.pass_gate is False

    def test_fail_programmatic(self):
        sc = self._make_scorecard(programmatic_pass=False)
        assert sc.pass_gate is False

    def test_boundary_recall_70(self):
        sc = self._make_scorecard(strengths_recall=0.70)
        assert sc.pass_gate is True

    def test_boundary_precision_70(self):
        sc = self._make_scorecard(strengths_precision=0.70)
        assert sc.pass_gate is True

    def test_boundary_alt_question_3(self):
        sc = self._make_scorecard(alt_question_mean_score=3.0)
        assert sc.pass_gate is True
