"""Smoke tests for the eval harness CLI (E14)."""

import importlib
import subprocess
import sys
from pathlib import Path

EVAL_SCRIPT = Path(__file__).parent.parent / "eval_synthesis.py"
GOLDEN_EXAMPLE = Path(__file__).parent.parent / "golden_sessions.example.json"

sys.path.insert(0, str(EVAL_SCRIPT.parent))
eval_synthesis = importlib.import_module("eval_synthesis")


class TestHarnessMockMode:
    """Tests for eval_synthesis.py --mock mode."""

    def test_mock_produces_scorecard(self, tmp_path: Path):
        """Mock mode writes a valid scorecard markdown file."""
        out_path = tmp_path / "scorecard-test.md"
        result = subprocess.run(
            [
                sys.executable,
                str(EVAL_SCRIPT),
                "--golden",
                str(GOLDEN_EXAMPLE),
                "--out",
                str(out_path),
                "--mock",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "# Synthesis Quality Scorecard" in content
        assert "PASS" in content

    def test_mock_scorecard_structure(self, tmp_path: Path):
        """Mock mode scorecard contains expected sections."""
        out_path = tmp_path / "scorecard-structure.md"
        subprocess.run(
            [
                sys.executable,
                str(EVAL_SCRIPT),
                "--golden",
                str(GOLDEN_EXAMPLE),
                "--out",
                str(out_path),
                "--mock",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        content = out_path.read_text(encoding="utf-8")
        assert "Strengths recall" in content
        assert "Strengths precision" in content
        assert "Alt-question mean" in content
        assert "Programmatic checks" in content
        assert "Per-Session Rubric" in content

    def test_mock_reports_session_count(self, tmp_path: Path):
        """Mock mode reports correct session count."""
        out_path = tmp_path / "scorecard-count.md"
        result = subprocess.run(
            [
                sys.executable,
                str(EVAL_SCRIPT),
                "--golden",
                str(GOLDEN_EXAMPLE),
                "--out",
                str(out_path),
                "--mock",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        assert "4 golden sessions" in result.stdout

    def test_missing_golden_file_fails(self, tmp_path: Path):
        """CLI exits with error on missing golden file."""
        out_path = tmp_path / "scorecard.md"
        result = subprocess.run(
            [
                sys.executable,
                str(EVAL_SCRIPT),
                "--golden",
                str(tmp_path / "nonexistent.json"),
                "--out",
                str(out_path),
                "--mock",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        assert result.returncode != 0

    def test_live_without_key_fails(self, tmp_path: Path):
        """CLI --live fails gracefully without OPENAI_API_KEY."""
        out_path = tmp_path / "scorecard.md"
        env = {"PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            [
                sys.executable,
                str(EVAL_SCRIPT),
                "--golden",
                str(GOLDEN_EXAMPLE),
                "--out",
                str(out_path),
                "--live",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
            env=env,
        )
        assert result.returncode != 0

    def test_live_uses_session_synthesizer(self, monkeypatch):
        """Live mode calls SessionSynthesizer and scores automatic axes."""

        class FakeSynthesizer:
            model = "fake-live-model"
            _hash = "fake-prompt-hash"

            async def synthesize(self, **kwargs):
                messages = kwargs["messages"]
                assert kwargs["scenario"] == "분수 덧셈"
                assert kwargs["misconception"] == "분자/분모를 각각 더함"
                return (
                    {
                        "version": 1,
                        "brief_feedback": ["좋은 질문을 사용했어요."],
                        "strengths": [
                            {
                                "message_id": 1,
                                "quote": messages[0]["content"],
                                "reason": "풀이 과정을 확인했어요.",
                            }
                        ],
                        "improvements": [
                            {
                                "student_message_id": 2,
                                "student_quote": messages[1]["content"],
                                "missed_reason": "오개념 단서가 있었어요.",
                                "alternative_question": (
                                    "왜 분모끼리 더해도 된다고 생각했어?"
                                ),
                                "alternative_reason": "생각의 근거를 확인해요.",
                            }
                        ],
                        "dialogue_coaching": [
                            {
                                "message_id": 1,
                                "role": "teacher",
                                "marker": "good_moment",
                                "note": "좋은 시작이에요.",
                            }
                        ],
                    },
                    "ok",
                )

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        session = eval_synthesis.GoldenSession(
            session_id="test-live",
            scenario_title="분수 덧셈",
            misconception="분자/분모를 각각 더함",
            messages=[
                {
                    "role": "teacher",
                    "content": "어떻게 계산했어?",
                    "id": 1,
                },
                {
                    "role": "student",
                    "content": "분자끼리 더하고 분모끼리 더했어요.",
                    "id": 2,
                },
            ],
            expected_labels={
                "strengths_ideal": [1],
                "improvements_ideal": [2],
            },
        )

        scorecard = eval_synthesis._run_live(
            [session],
            synthesizer_cls=FakeSynthesizer,
        )

        assert scorecard.model == "fake-live-model"
        assert scorecard.prompt_hash == "fake-prompt-hash"
        assert scorecard.strengths_recall == 1.0
        assert scorecard.strengths_precision == 1.0
        assert scorecard.programmatic_pass is True
        assert scorecard.rubric_scores[0].length == 5.0
        assert scorecard.rubric_scores[0].verbatim_integrity == 5.0
        assert scorecard.rubric_scores[0].message_id_validity == 5.0
        assert scorecard.alt_question_mean_score == 0.0
        assert "alternative_questions" in scorecard.live_outputs[0]
