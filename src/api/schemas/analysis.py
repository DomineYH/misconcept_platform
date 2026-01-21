"""Pydantic schemas for analysis API responses.

Structured reasoning models for enhanced question analysis with
pedagogical, cognitive, and contextual perspectives.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PedagogicalAnalysis(BaseModel):
    """교육학적 관점 분석."""

    educational_principle: str = Field(
        ..., description="이 질문이 반영하는 교육 원리"
    )
    effectiveness: str = Field(
        ..., description="이 질문 유형의 효과성 분석"
    )
    improvement_suggestion: Optional[str] = Field(
        None, description="교육학적 개선 제안"
    )


class CognitiveAnalysis(BaseModel):
    """인지적 관점 분석."""

    cognitive_demand: str = Field(
        ..., description="Bloom's Taxonomy 수준"
    )
    student_response_prediction: str = Field(
        ..., description="예상 학생 반응"
    )
    misconception_addressing: str = Field(
        ..., description="오개념 대응 방식"
    )


class ContextualAnalysis(BaseModel):
    """맥락적 관점 분석."""

    dialogue_role: str = Field(
        ..., description="대화 흐름 내 역할"
    )
    timing_appropriateness: str = Field(
        ..., description="타이밍 적절성"
    )
    connection_to_prior: str = Field(
        ..., description="이전 발화와의 연결"
    )


class DetailedReasoning(BaseModel):
    """구조화된 분류 이유 (3가지 관점)."""

    summary: str = Field(..., description="분류 요약")
    pedagogical: Optional[PedagogicalAnalysis] = Field(
        None, description="교육학적 분석"
    )
    cognitive: Optional[CognitiveAnalysis] = Field(
        None, description="인지적 분석"
    )
    contextual: Optional[ContextualAnalysis] = Field(
        None, description="맥락적 분석"
    )


class QuestionAnalysisResponse(BaseModel):
    """단일 질문 분석 응답."""

    content: str = Field(..., description="교사 질문 내용")
    label: str = Field(..., description="분류 레이블")
    confidence: Optional[float] = Field(None, description="신뢰도 (0.0-1.0)")
    reasoning: Optional[DetailedReasoning] = Field(
        None, description="상세 분석 이유"
    )
    created_at: str = Field(..., description="생성 시간")


class SessionAnalysisResponse(BaseModel):
    """세션 분석 응답."""

    distribution: dict[str, int] = Field(
        ..., description="레이블별 분포"
    )
    feedback: Optional[str] = Field(None, description="전체 피드백")
    questions: list[QuestionAnalysisResponse] = Field(
        default_factory=list, description="질문별 분석 목록"
    )
    session_ended_at: str = Field(..., description="세션 종료 시간")


class AnalysisListItem(BaseModel):
    """관리자 페이지용 분석 목록 항목."""

    id: int
    content: str
    label: str
    confidence: float
    reasoning: Optional[DetailedReasoning] = None
    session_id: int
    scenario_title: str
    created_at: datetime
