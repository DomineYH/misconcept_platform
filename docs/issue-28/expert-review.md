# Issue #28 — Expert Review Protocol

## Purpose

Before any UI code ships for the analysis report redesign, a math-education
expert must validate that the LLM-generated coaching is pedagogically sound.
This document describes the external prerequisite, what the expert must do,
what good looks like, and how to record sign-off.

## Expert Prerequisite

**Required expert profile:** Math-education faculty at 대구교육대학교
(or equivalent math-ed specialist) familiar with 분수 오개념 pedagogy.

## What the Expert Must Do

### Step 1 — Review Golden Session Labels

1. Open `evals/issue-28/golden_sessions.example.json`.
2. For each session, review the `expected_labels`:
   - **`strengths_ideal`**: Are these the right teacher messages
     to highlight as 우수한 점?
   - **`improvements_ideal`**: Are these the right student messages
     to highlight as 개선할 점? Is the alternative question appropriate?
   - **`dialogue_markers_ideal`**: Are the good_moment / missed_moment /
     key_clue markers correctly placed?
3. Edit the file directly or provide corrections in a separate document.

### Step 2 — Score Alternative Questions

After a `--live` harness run produces a scorecard, the expert must:

1. Review each `alternative_question` in the LLM output.
2. Score on a 0–5 scale for:
   - Mathematical correctness
   - Pedagogical soundness (Socratic, non-leading)
   - Tone (warm, appropriate register)
3. Record scores in the scorecard's expert_labels section.

### Step 3 — Sign Off

Record sign-off as one of:

- A commit adding `evals/issue-28/scorecards/expert-signoff-{date}.md`
  containing the expert's name, date, and "APPROVED" or "REVISED" verdict.
- A PR comment from a named math-ed reviewer stating the rubric results
  are acceptable.
- An email thread forwarded to the project repo owner.

## What Good Looks Like

| Metric | Threshold | How to Verify |
|--------|-----------|---------------|
| Strengths recall | ≥ 70% | Harness computes automatically |
| Strengths precision | ≥ 70% | Harness computes automatically |
| Alternative question quality | Mean ≥ 3.0/5.0 | Expert scores manually |
| Verbatim quote integrity | 100% | Harness checks programmatically |
| Message ID validity | 100% | Harness checks programmatically |

## Quality Gate Flow

```
1. Expert reviews golden session labels → refined JSON
2. Run harness: python -m evals.issue_28.eval_synthesis \
      --golden golden_sessions.json --out scorecard.md --live
3. Expert scores alternative questions → updated scorecard
4. Expert signs off → signoff document committed
5. If gate fails → iterate on prompt, re-run from step 2
6. Gate passes → UI implementation may begin
```

## Status

- [ ] Golden session labels reviewed by expert
- [ ] Live harness run completed
- [ ] Alternative questions scored by expert
- [ ] Sign-off recorded
- [ ] Quality gate: PASS

**Current state:** Awaiting expert review.
Placeholder labels in `golden_sessions.example.json` are NOT expert-validated.
