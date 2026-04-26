"""Issue #28 — Session synthesis evaluation harness (E14).

CLI that runs the synthesis against a golden session set and emits
a markdown scorecard.

Usage:
    python -m evals.issue-28.eval_synthesis --golden PATH --out PATH --mock
    python -m evals.issue-28.eval_synthesis --golden PATH --out PATH --live

Modes:
    --mock  Deterministic stub payload (no LLM call).
    --live  Real LLM call via OPENAI_API_KEY.

DO NOT run --live without expert-reviewed golden session labels.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# evals/issue-28 has a hyphen — not importable as a package.
# Add the script's directory to sys.path for direct imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from schemas import (  # noqa: E402
    GoldenSession,
    RubricScore,
    Scorecard,
)

MOCK_PAYLOAD = {
    "version": 1,
    "brief_feedback": [
        "지수의 풀이 과정을 물어본 것은 좋은 시작이었어요.",
        "분자끼리 더했다는 답변에서 오개념의 핵심을 발견했어요.",
        "다음에는 핵심 단어를 잡아서 되물어보면 더 좋겠어요.",
    ],
    "strengths": [
        {
            "message_id": 1,
            "quote": "어떻게 답을 구했어?",
            "reason": "대화의 첫 질문으로 풀이 과정을 탐색했어요.",
        }
    ],
    "improvements": [
        {
            "student_message_id": 2,
            "student_quote": "분자끼리 더하고 분모끼리 더했어요",
            "missed_reason": "이 답변에 오개념의 핵심 단서가 있었어요.",
            "alternative_question": "왜 분자끼리 더해도 된다고 생각했어?",
            "alternative_reason": (
                "학생의 답변 속 핵심 단어를 잡아서 " "되물으면 좋아요."
            ),
        }
    ],
    "dialogue_coaching": [
        {
            "message_id": 1,
            "role": "teacher",
            "marker": "good_moment",
            "note": "첫 질문으로 풀이 과정을 탐색했어요.",
        },
        {
            "message_id": 2,
            "role": "student",
            "marker": "key_clue",
            "note": "오개념 핵심 단서가 드러난 순간이에요.",
        },
    ],
}


def _run_mock(golden_sessions: list[GoldenSession]) -> Scorecard:
    """Produce a scorecard using deterministic stub payload."""
    rubric_scores = []
    total_recall = 0.0
    total_precision = 0.0
    n = len(golden_sessions)

    for gs in golden_sessions:
        # In mock mode, assume perfect alignment with placeholder labels
        rubric = RubricScore(
            session_id=gs.session_id,
            mathematical_correctness=5.0,
            pedagogical_soundness=5.0,
            tone=5.0,
            length=5.0,
            verbatim_integrity=5.0,
            message_id_validity=5.0,
        )
        rubric_scores.append(rubric)
        total_recall += 1.0
        total_precision += 1.0

    return Scorecard(
        timestamp=datetime.now(timezone.utc).isoformat(),
        model="mock",
        prompt_hash="mock-hash",
        n_sessions=n,
        strengths_recall=total_recall / max(n, 1),
        strengths_precision=total_precision / max(n, 1),
        alt_question_mean_score=5.0,
        programmatic_pass=True,
        rubric_scores=rubric_scores,
    )


def _run_live(golden_sessions: list[GoldenSession]) -> Scorecard:
    """Run real synthesis against golden sessions.

    Gated on OPENAI_API_KEY env var.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key.startswith("sk-"):
        print(
            "ERROR: OPENAI_API_KEY not set. Cannot run --live mode.",
            file=sys.stderr,
        )
        sys.exit(1)

    # TODO: Import and call SessionSynthesizer once Stage C is complete.
    # For now, --live is intentionally unimplemented.
    raise NotImplementedError(
        "--live mode requires SessionSynthesizer "
        "(Stage C — not yet implemented)"
    )


def _render_scorecard_md(scorecard: Scorecard) -> str:
    """Render scorecard as markdown."""
    lines = [
        "# Synthesis Quality Scorecard",
        "",
        f"- **Timestamp**: {scorecard.timestamp}",
        f"- **Model**: {scorecard.model}",
        f"- **Prompt hash**: {scorecard.prompt_hash}",
        f"- **Sessions evaluated**: {scorecard.n_sessions}",
        f"- **Gate result**: "
        f"{'✅ PASS' if scorecard.pass_gate else '❌ FAIL'}",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value | Threshold |",
        "|--------|-------|-----------|",
        f"| Strengths recall | " f"{scorecard.strengths_recall:.1%} | ≥ 70% |",
        f"| Strengths precision | "
        f"{scorecard.strengths_precision:.1%} | ≥ 70% |",
        f"| Alt-question mean | "
        f"{scorecard.alt_question_mean_score:.1f}/5 | ≥ 3.0 |",
        f"| Programmatic checks | "
        f"{'PASS' if scorecard.programmatic_pass else 'FAIL'} "
        f"| 100% |",
        "",
        "## Per-Session Rubric",
        "",
        "| Session | Math | Pedagogy | Tone | Length "
        "| Verbatim | MsgID | Mean |",
        "|---------|------|----------|------|--------"
        "|----------|-------|------|",
    ]
    for rs in scorecard.rubric_scores:
        lines.append(
            f"| {rs.session_id} "
            f"| {rs.mathematical_correctness:.1f} "
            f"| {rs.pedagogical_soundness:.1f} "
            f"| {rs.tone:.1f} "
            f"| {rs.length:.1f} "
            f"| {rs.verbatim_integrity:.1f} "
            f"| {rs.message_id_validity:.1f} "
            f"| {rs.mean:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Issue #28 synthesis evaluation harness",
    )
    parser.add_argument(
        "--golden",
        required=True,
        help="Path to golden sessions JSON file",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for markdown scorecard",
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic stub payload (no LLM)",
    )
    mode_group.add_argument(
        "--live",
        action="store_true",
        help="Run real LLM synthesis (requires OPENAI_API_KEY)",
    )
    args = parser.parse_args()

    # Load golden sessions
    golden_path = Path(args.golden)
    if not golden_path.exists():
        print(f"ERROR: {golden_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(golden_path, encoding="utf-8") as f:
        raw = json.load(f)

    golden_sessions = [GoldenSession(**gs) for gs in raw]
    print(f"Loaded {len(golden_sessions)} golden sessions")

    # Run eval
    if args.mock:
        scorecard = _run_mock(golden_sessions)
    else:
        scorecard = _run_live(golden_sessions)

    # Render and write
    md = _render_scorecard_md(scorecard)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"Scorecard written to {out_path}")
    print(f"Gate: {'PASS' if scorecard.pass_gate else 'FAIL'}")


if __name__ == "__main__":
    main()
