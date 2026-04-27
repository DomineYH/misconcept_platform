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
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# evals/issue-28 has a hyphen — not importable as a package.
# Add the script's directory to sys.path for direct imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Also support direct script execution from outside the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
                "학생의 답변 속 핵심 단어를 잡아서 되물으면 좋아요."
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


def _run_live(
    golden_sessions: list[GoldenSession],
    synthesizer_cls: type[Any] | None = None,
) -> Scorecard:
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

    return asyncio.run(_run_live_async(golden_sessions, synthesizer_cls))


async def _run_live_async(
    golden_sessions: list[GoldenSession],
    synthesizer_cls: type[Any] | None = None,
) -> Scorecard:
    """Run SessionSynthesizer and compute automatic scorecard metrics."""
    if synthesizer_cls is None:
        from src.services.session_synthesizer import SessionSynthesizer

        synthesizer_cls = SessionSynthesizer

    synthesizer = synthesizer_cls()

    rubric_scores = []
    live_outputs = []
    total_expected_strengths = 0
    total_matched_strengths = 0
    total_output_strengths = 0
    total_output_strength_matches = 0
    total_alt_question_score = 0.0
    total_alt_questions = 0
    programmatic_pass = True

    for gs in golden_sessions:
        messages = [msg.model_dump() for msg in gs.messages]
        payload, status = await synthesizer.synthesize(
            messages=messages,
            question_analyses=None,
            scenario=gs.scenario_title,
            misconception=gs.misconception,
            framework=None,
        )

        expected_strengths = set(gs.expected_labels.strengths_ideal)
        output_strengths = {
            item.get("message_id")
            for item in payload.get("strengths", [])
            if isinstance(item, dict)
        }
        matched_strengths = expected_strengths & output_strengths
        output_strength_matches = output_strengths & expected_strengths

        total_expected_strengths += len(expected_strengths)
        total_matched_strengths += len(matched_strengths)
        total_output_strengths += len(output_strengths)
        total_output_strength_matches += len(output_strength_matches)

        checks = _score_programmatic_axes(payload, messages)
        programmatic_pass = programmatic_pass and checks["programmatic_pass"]

        alt_questions = _collect_alternative_questions(payload)
        total_alt_questions += len(alt_questions)
        # Expert quality scoring is intentionally not automated. The harness
        # exposes live outputs below so a math-ed reviewer can score axes 1-3.
        total_alt_question_score += 0.0

        rubric_scores.append(
            RubricScore(
                session_id=gs.session_id,
                mathematical_correctness=0.0,
                pedagogical_soundness=0.0,
                tone=0.0,
                length=checks["length_score"],
                verbatim_integrity=checks["verbatim_score"],
                message_id_validity=checks["message_id_score"],
            )
        )
        live_outputs.append(
            {
                "session_id": gs.session_id,
                "status": status,
                "payload": payload,
                "alternative_questions": alt_questions,
                "expert_scoring_note": (
                    "Axes 1-3 require manual math-education expert scoring."
                ),
            }
        )

    strengths_recall = (
        total_matched_strengths / total_expected_strengths
        if total_expected_strengths
        else 1.0
    )
    strengths_precision = (
        total_output_strength_matches / total_output_strengths
        if total_output_strengths
        else 1.0
    )
    alt_question_mean_score = (
        total_alt_question_score / total_alt_questions
        if total_alt_questions
        else 0.0
    )

    return Scorecard(
        timestamp=datetime.now(timezone.utc).isoformat(),
        model=getattr(synthesizer, "model", "unknown"),
        prompt_hash=getattr(synthesizer, "_hash", "unknown"),
        n_sessions=len(golden_sessions),
        strengths_recall=strengths_recall,
        strengths_precision=strengths_precision,
        alt_question_mean_score=alt_question_mean_score,
        programmatic_pass=programmatic_pass,
        rubric_scores=rubric_scores,
        live_outputs=live_outputs,
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
        f"- **Gate result**: {'✅ PASS' if scorecard.pass_gate else '❌ FAIL'}",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value | Threshold |",
        "|--------|-------|-----------|",
        f"| Strengths recall | {scorecard.strengths_recall:.1%} | ≥ 70% |",
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
    if scorecard.live_outputs:
        lines.extend(
            [
                "",
                "## Live Outputs for Expert Review",
                "",
                (
                    "Axes 1–3 (mathematical correctness, pedagogical "
                    "soundness, tone) are set to 0.0 until a math-education "
                    "expert scores the generated alternative questions."
                ),
            ]
        )
        for output in scorecard.live_outputs:
            payload = output.get("payload", {})
            lines.extend(
                [
                    "",
                    f"### {output.get('session_id', 'unknown')}",
                    "",
                    (
                        "- **Synthesis status**: "
                        f"{output.get('status', 'unknown')}"
                    ),
                    "",
                    "#### Alternative Questions",
                    "",
                ]
            )
            alt_questions = output.get("alternative_questions", [])
            if alt_questions:
                for item in alt_questions:
                    lines.append(
                        f"- Message {item.get('student_message_id')}: "
                        f"{item.get('alternative_question', '')}"
                    )
            else:
                lines.append("- None")
            lines.extend(["", "#### Payload", "", "```json"])
            lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
            lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _score_programmatic_axes(
    payload: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, float | bool]:
    """Score automatic rubric axes for a synthesis payload."""
    valid_ids = {msg.get("id") for msg in messages}
    content_by_id = {msg.get("id"): msg.get("content", "") for msg in messages}

    message_ids_valid = True
    quotes_verbatim = True
    length_valid = True

    for item in payload.get("brief_feedback", []):
        if not isinstance(item, str) or len(item) > 70:
            length_valid = False

    for item in payload.get("strengths", []):
        if not isinstance(item, dict):
            message_ids_valid = False
            quotes_verbatim = False
            continue
        message_id = item.get("message_id")
        if message_id not in valid_ids:
            message_ids_valid = False
            continue
        quote = item.get("quote", "")
        if not isinstance(quote, str) or quote not in content_by_id[message_id]:
            quotes_verbatim = False
        reason = item.get("reason", "")
        if isinstance(reason, str) and len(reason) > 200:
            length_valid = False

    for item in payload.get("improvements", []):
        if not isinstance(item, dict):
            message_ids_valid = False
            continue
        if item.get("student_message_id") not in valid_ids:
            message_ids_valid = False
        alt_question = item.get("alternative_question", "")
        if not isinstance(alt_question, str) or len(alt_question) > 60:
            length_valid = False
        for key in ("missed_reason", "alternative_reason"):
            reason = item.get(key, "")
            if isinstance(reason, str) and len(reason) > 200:
                length_valid = False

    for item in payload.get("dialogue_coaching", []):
        if not isinstance(item, dict):
            message_ids_valid = False
            continue
        if item.get("message_id") not in valid_ids:
            message_ids_valid = False

    return {
        "length_score": 5.0 if length_valid else 0.0,
        "verbatim_score": 5.0 if quotes_verbatim else 0.0,
        "message_id_score": 5.0 if message_ids_valid else 0.0,
        "programmatic_pass": quotes_verbatim and message_ids_valid,
    }


def _collect_alternative_questions(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract generated alternative questions for expert scoring."""
    questions = []
    for item in payload.get("improvements", []):
        if not isinstance(item, dict):
            continue
        questions.append(
            {
                "student_message_id": item.get("student_message_id"),
                "alternative_question": item.get("alternative_question", ""),
            }
        )
    return questions


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
