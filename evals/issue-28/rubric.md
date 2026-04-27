# Issue #28 — Session Synthesis Quality Rubric

6-axis scoring for evaluating `synthesize_session_feedback` output
against expert-labeled golden sessions.

## Axes (each scored 0–5)

### 1. Mathematical Correctness

Are the `alternative_question` entries mathematically accurate for
the misconception domain (분수 덧셈, etc.)?

| Score | Meaning |
|-------|---------|
| 0 | Contains mathematical errors |
| 1 | Mostly wrong, some correct elements |
| 2 | Partially correct but misleading |
| 3 | Correct but not precise |
| 4 | Correct and precise |
| 5 | Correct, precise, and elegant |

### 2. Pedagogical Soundness

Does the coaching respect Socratic/ZPD principles?
Is it non-leading? Does it guide without telling?

| Score | Meaning |
|-------|---------|
| 0 | Directly tells the answer |
| 1 | Highly leading questions |
| 2 | Somewhat leading |
| 3 | Neutral, neither guiding nor leading |
| 4 | Guides student thinking effectively |
| 5 | Exemplary Socratic scaffolding |

### 3. Tone

Warm, encouraging, appropriate Korean register for pre-service
teachers at 교육대학교. Short sentences.

| Score | Meaning |
|-------|---------|
| 0 | Inappropriate or harsh |
| 1 | Cold or robotic |
| 2 | Neutral but not warm |
| 3 | Adequately warm |
| 4 | Warm and encouraging |
| 5 | Exemplary coaching tone |

### 4. Length

`alternative_question` ≤ 60 Korean chars.
`reason` ≤ 200 Korean chars.
`brief_feedback` items ≤ 70 Korean chars each.

| Score | Meaning |
|-------|---------|
| 0 | All items violate length bounds |
| 1 | Most items too long |
| 2 | Mixed compliance |
| 3 | Most items within bounds |
| 4 | All within bounds, minor excess |
| 5 | All within bounds, concise |

### 5. Verbatim Quote Integrity

Each `strengths[].quote` must appear **verbatim** in the referenced
message content. Checked programmatically.

| Score | Meaning |
|-------|---------|
| 0 | No quotes match |
| 5 | All quotes match verbatim |

### 6. Message ID Validity

All `message_id` references must exist in the session.
No hallucinated IDs. Checked programmatically.

| Score | Meaning |
|-------|---------|
| 0 | Hallucinated IDs present |
| 5 | All IDs valid |

## Quality Gate Thresholds

The synthesis must pass ALL of these before UI code ships:

| Metric | Threshold |
|--------|-----------|
| Strengths recall | ≥ 70% of expert-labeled items surface |
| Strengths precision | ≥ 70% of LLM items have expert match |
| Alternative question mean rubric | ≥ 3.0 / 5.0 |
| Programmatic checks (verbatim + ID) | 100% pass |

## Expert Scoring Protocol

1. Expert receives each `alternative_question` from LLM output.
2. Expert scores axes 1-3 independently (0-5).
3. Axes 4-6 are computed programmatically by the harness.
4. Harness aggregates into a `Scorecard`.
5. If gate fails, iterate on the prompt and re-run.
