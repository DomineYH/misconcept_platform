import json
from typing import Final

from src.models import Message, QuestionAnalysis

DEGRADED_CLASSIFICATION_LABEL: Final = "분류 실패"


def build_degraded_question_analysis(
    msg: Message,
    error: Exception,
) -> QuestionAnalysis:
    meta = {
        "status": "degraded",
        "summary": ("분류에 실패해 이 교사 메시지는 자동 분류되지 않았습니다."),
        "improved_sentence": None,
        "error_type": type(error).__name__,
        "error": str(error),
    }
    return QuestionAnalysis(
        message_id=msg.id,
        label=DEGRADED_CLASSIFICATION_LABEL,
        confidence=0.0,
        meta_json=json.dumps(meta, ensure_ascii=False),
        grade=None,
    )
