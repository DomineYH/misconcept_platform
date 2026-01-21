"""Dynamic few-shot example generation for framework-aware analysis.

This module generates few-shot examples using actual framework labels
instead of hardcoded labels like "Pressing", "Linking", etc.
"""

import json
from typing import Optional


# Semantic category keywords for label classification
HIGH_LEVERAGE_KEYWORDS = [
    "pressing",
    "probing",
    "high",
    "quality",
    "deep",
    "critical",
    "elaborat",
    "explor",
    "reason",
]
LOW_LEVERAGE_KEYWORDS = [
    "recall",
    "low",
    "basic",
    "simple",
    "factual",
    "remember",
    "closed",
    "yes/no",
]
MEDIUM_LEVERAGE_KEYWORDS = [
    "linking",
    "connecting",
    "directing",
    "medium",
    "guide",
    "scaffold",
    "support",
    "neutral",
]

# Example templates for each semantic category with structured reasoning
EXAMPLE_TEMPLATES = {
    "high_leverage": {
        "question": (
            "What happens to the moon's shadow during a solar eclipse?"
        ),
        "reasoning": {
            "summary": "학생이 자신의 사고 모델과 추론을 명확히 표현하도록 유도하는 질문",
            "pedagogical": {
                "educational_principle": "구성주의 - 학생이 표현을 통해 이해를 구축함",
                "effectiveness": "높음 - 능동적 지식 구성을 촉진함",
                "improvement_suggestion": None,
            },
            "cognitive": {
                "cognitive_demand": "분석",
                "student_response_prediction": "학생은 그림자 역학에 대한 자신의 이해를 설명해야 함",
                "misconception_addressing": "일식 메커니즘에 대한 이해를 직접적으로 탐색함",
            },
            "contextual": {
                "dialogue_role": "사고를 드러내기 위한 탐색 질문",
                "timing_appropriateness": "맥락 설정 후 적절함",
                "connection_to_prior": "천체에 대한 이전 논의를 기반으로 함",
            },
        },
    },
    "medium_leverage": {
        "question": (
            "How does your explanation connect to what you said earlier "
            "about the topic?"
        ),
        "reasoning": {
            "summary": "학생이 아이디어를 연결하고 일관된 이해를 구축하도록 유도하는 질문",
            "pedagogical": {
                "educational_principle": "비계 설정 - 학생을 연결로 안내함",
                "effectiveness": "중간 - 사고 정리에 도움이 되지만 방향을 제시함",
                "improvement_suggestion": "어떤 이전 발언인지 더 구체적으로 명시할 수 있음",
            },
            "cognitive": {
                "cognitive_demand": "이해",
                "student_response_prediction": "학생이 이전 발언을 검토하고 연결함",
                "misconception_addressing": "일관성 촉진을 통해 간접적으로 다룸",
            },
            "contextual": {
                "dialogue_role": "연결 질문",
                "timing_appropriateness": "여러 번의 교환 후 좋은 타이밍",
                "connection_to_prior": "이전 대화를 명시적으로 참조함",
            },
        },
    },
    "low_leverage": {
        "question": "Is the Earth bigger than the moon?",
        "reasoning": {
            "summary": "깊은 사고 없이 단순한 사실 회상만 요구하는 질문",
            "pedagogical": {
                "educational_principle": "직접 교수법 - 사실적 지식 확인",
                "effectiveness": "낮음 - 개념적 이해를 촉진하지 않음",
                "improvement_suggestion": "'크기 차이가 어떤 영향을...'으로 질문할 수 있음",
            },
            "cognitive": {
                "cognitive_demand": "기억",
                "student_response_prediction": "학생이 예/아니오 답변을 제공함",
                "misconception_addressing": "근본적인 추론을 다루지 않음",
            },
            "contextual": {
                "dialogue_role": "사실 확인 질문",
                "timing_appropriateness": "더 깊은 탐색이 필요할 수 있음; 시기상조일 수 있음",
                "connection_to_prior": "진행 중인 논의와 제한적 연결",
            },
        },
    },
}


def classify_label_category(label: str, description: str = "") -> str:
    """
    Map a framework label to a semantic category.

    Args:
        label: Framework label (e.g., "Pressing", "HighQuality")
        description: Optional framework description for context

    Returns:
        Category string: "high_leverage", "medium_leverage", or "low_leverage"
    """
    # Combine label and description for matching
    combined = f"{label} {description}".lower()

    # Check high-leverage keywords
    for keyword in HIGH_LEVERAGE_KEYWORDS:
        if keyword in combined:
            return "high_leverage"

    # Check low-leverage keywords
    for keyword in LOW_LEVERAGE_KEYWORDS:
        if keyword in combined:
            return "low_leverage"

    # Check medium-leverage keywords
    for keyword in MEDIUM_LEVERAGE_KEYWORDS:
        if keyword in combined:
            return "medium_leverage"

    # Default to medium if no match
    return "medium_leverage"


def generate_examples(
    labels: list[str], description: Optional[str] = None
) -> str:
    """
    Generate few-shot examples using actual framework labels.

    Args:
        labels: List of framework labels
        description: Optional framework description

    Returns:
        Formatted string of few-shot examples using actual labels
    """
    if not labels:
        return ""

    description = description or ""
    examples = []
    used_categories = set()

    # Map each label to a category and generate example
    label_categories = {}
    for label in labels:
        category = classify_label_category(label, description)
        label_categories[label] = category

    # Generate examples for distinct categories (max 3)
    example_num = 1
    for label in labels:
        category = label_categories[label]

        # Skip if we've already used this category
        if category in used_categories:
            continue

        used_categories.add(category)
        template = EXAMPLE_TEMPLATES.get(
            category, EXAMPLE_TEMPLATES["medium_leverage"]
        )

        # Format reasoning as JSON string for structured output
        reasoning_json = json.dumps(
            template["reasoning"], ensure_ascii=False, indent=2
        )

        example = f"""Example {example_num}:
Teacher: "{template['question']}"
Classification: {label}
Confidence: 0.{85 + example_num * 3}
Reasoning: {reasoning_json}"""

        examples.append(example)
        example_num += 1

        # Maximum 3 examples
        if example_num > 3:
            break

    # If we have less than 2 examples, add more from remaining labels
    if len(examples) < 2 and len(labels) > len(examples):
        remaining_labels = [
            lbl
            for lbl in labels
            if lbl
            not in [
                ex.split("Classification: ")[1].split("\n")[0] for ex in examples
            ]
        ]
        for label in remaining_labels[: 2 - len(examples)]:
            category = label_categories.get(label, "medium_leverage")
            template = EXAMPLE_TEMPLATES.get(
                category, EXAMPLE_TEMPLATES["medium_leverage"]
            )

            # Format reasoning as JSON string
            reasoning_json = json.dumps(
                template["reasoning"], ensure_ascii=False, indent=2
            )

            example = f"""Example {example_num}:
Teacher: "{template['question']}"
Classification: {label}
Confidence: 0.{85 + example_num * 3}
Reasoning: {reasoning_json}"""

            examples.append(example)
            example_num += 1

    return "\n\n".join(examples)
