"""Pydantic v2 schemas for issue-28 eval harness (E14).

GoldenSession  — expert-labeled session used as ground truth.
ExpertLabel    — per-session expected strengths/improvements/markers.
RubricScore    — per-axis 0-5 score for a single synthesis output.
Scorecard      — aggregate scorecard across all golden sessions.
"""

from pydantic import BaseModel, Field


class DialogueMessage(BaseModel):
    """A single message in a golden session."""

    role: str = Field(
        ...,
        description="teacher | student | tutor",
    )
    content: str
    id: int = Field(
        ...,
        description="Stable message ID used by expert labels",
    )


class ExpectedLabels(BaseModel):
    """Expert-labeled ground truth for a session."""

    strengths_ideal: list[int] = Field(
        default_factory=list,
        description="Message IDs of teacher questions that should "
        "appear in 우수한 점",
    )
    improvements_ideal: list[int] = Field(
        default_factory=list,
        description="Student message IDs that should appear " "in 개선할 점",
    )
    dialogue_markers_ideal: list[dict] = Field(
        default_factory=list,
        description="Expected dialogue_coaching markers: "
        "[{message_id, marker}]",
    )


class GoldenSession(BaseModel):
    """A single expert-labeled session for eval.

    The `expected_labels` contain placeholder data until a math-ed
    expert (대구교육대학교 faculty) refines them.
    """

    session_id: str = Field(
        ...,
        description="Unique identifier for the golden session",
    )
    scenario_title: str
    misconception: str = Field(
        ...,
        description="Target misconception (e.g. 분수 덧셈 오개념)",
    )
    messages: list[DialogueMessage] = Field(
        ...,
        min_length=1,
    )
    expected_labels: ExpectedLabels = Field(
        default_factory=ExpectedLabels,
    )


class ExpertLabel(BaseModel):
    """Expert's rubric judgment on a single alternative_question."""

    session_id: str
    alternative_question: str
    score: float = Field(
        ...,
        ge=0.0,
        le=5.0,
        description="Expert 0-5 score for alternative question "
        "quality (math correctness + pedagogical soundness)",
    )
    notes: str = Field(default="")


class RubricScore(BaseModel):
    """Per-axis 0-5 score for one synthesis output."""

    session_id: str
    mathematical_correctness: float = Field(..., ge=0.0, le=5.0)
    pedagogical_soundness: float = Field(..., ge=0.0, le=5.0)
    tone: float = Field(..., ge=0.0, le=5.0)
    length: float = Field(..., ge=0.0, le=5.0)
    verbatim_integrity: float = Field(..., ge=0.0, le=5.0)
    message_id_validity: float = Field(..., ge=0.0, le=5.0)

    @property
    def mean(self) -> float:
        """Mean across all 6 axes."""
        vals = [
            self.mathematical_correctness,
            self.pedagogical_soundness,
            self.tone,
            self.length,
            self.verbatim_integrity,
            self.message_id_validity,
        ]
        return sum(vals) / len(vals)


class Scorecard(BaseModel):
    """Aggregate scorecard across all golden sessions."""

    timestamp: str
    model: str
    prompt_hash: str
    n_sessions: int
    strengths_recall: float = Field(
        ...,
        description="Fraction of expert-labeled strengths found",
    )
    strengths_precision: float = Field(
        ...,
        description="Fraction of LLM strengths with expert match",
    )
    alt_question_mean_score: float = Field(
        ...,
        description="Mean expert rubric score for "
        "alternative questions (0-5)",
    )
    programmatic_pass: bool = Field(
        ...,
        description="100% pass on verbatim + message_id checks",
    )
    rubric_scores: list[RubricScore] = Field(default_factory=list)
    expert_labels: list[ExpertLabel] = Field(default_factory=list)

    @property
    def pass_gate(self) -> bool:
        """Whether the quality gate thresholds are met.

        Thresholds (per plan §5.0):
          - strengths recall >= 70%
          - strengths precision >= 70%
          - alt_question mean score >= 3.0
          - programmatic_pass == True
        """
        return (
            self.strengths_recall >= 0.70
            and self.strengths_precision >= 0.70
            and self.alt_question_mean_score >= 3.0
            and self.programmatic_pass
        )
