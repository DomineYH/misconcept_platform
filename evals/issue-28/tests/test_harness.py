"""Smoke tests for the eval harness CLI (E14)."""

import subprocess
import sys
from pathlib import Path

EVAL_SCRIPT = Path(__file__).parent.parent / "eval_synthesis.py"
GOLDEN_EXAMPLE = Path(__file__).parent.parent / "golden_sessions.example.json"


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
