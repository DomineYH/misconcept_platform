"""Dialogue analysis utilities for conversation monitoring."""

import re


def extract_recent_pairs(
    exchanges: list[dict], max_pairs: int = 3
) -> list[tuple[str, str]]:
    """Extract recent teacher-student dialogue pairs.

    Args:
        exchanges: List of exchange dicts with 'role' and 'content'
        max_pairs: Maximum number of pairs to extract (default: 3)

    Returns:
        List of (teacher_question, student_response) tuples
    """
    pairs = []
    i = len(exchanges) - 1

    while i >= 1 and len(pairs) < max_pairs:
        if (
            exchanges[i]["role"] == "student"
            and exchanges[i - 1]["role"] == "teacher"
        ):
            pairs.insert(
                0, (exchanges[i - 1]["content"], exchanges[i]["content"])
            )
            i -= 2
        else:
            i -= 1

    return pairs


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0

    # Tokenize: lowercase and split by whitespace/punctuation
    words1 = set(re.findall(r"\w+", text1.lower()))
    words2 = set(re.findall(r"\w+", text2.lower()))

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def detect_repetitive_dialogue_simple(
    pairs: list[tuple[str, str]], threshold: float = 0.7
) -> bool:
    """Detect repetitive dialogue using Jaccard similarity.

    Args:
        pairs: List of (teacher, student) dialogue pairs
        threshold: Similarity threshold (default: 0.7)

    Returns:
        True if repetitive pattern detected
    """
    if len(pairs) < 2:
        return False

    similar_count = 0
    for i in range(len(pairs) - 1):
        teacher_sim = calculate_jaccard_similarity(
            pairs[i][0], pairs[i + 1][0]
        )
        student_sim = calculate_jaccard_similarity(
            pairs[i][1], pairs[i + 1][1]
        )

        if teacher_sim > threshold or student_sim > threshold:
            similar_count += 1

    # At least 1 similar pair out of comparisons
    return similar_count >= 1


def check_low_leverage_patterns(question: str) -> bool:
    """Check for low-leverage question patterns.

    Args:
        question: Teacher's question

    Returns:
        True if low-leverage pattern detected
    """
    latest = question.lower()

    low_leverage_indicators = [
        # Too short question
        latest.endswith("?") and len(latest.split()) < 5,
        # Closed yes/no questions
        any(
            phrase in latest
            for phrase in ["yes or no", "is it", "are you", "do you"]
        ),
        # Directive statements
        "you should" in latest or "try this" in latest,
    ]

    return any(low_leverage_indicators)


def check_vague_patterns(recent_teacher_questions: list[str]) -> bool:
    """Check for vague/stagnant question patterns.

    Args:
        recent_teacher_questions: Recent teacher questions

    Returns:
        True if vague pattern detected
    """
    if len(recent_teacher_questions) < 3:
        return False

    recent_3 = recent_teacher_questions[-3:]
    vague_questions = [
        q
        for q in recent_3
        if any(
            phrase in q.lower()
            for phrase in [
                "what do you think",
                "any thoughts",
                "what else",
            ]
        )
    ]
    return len(vague_questions) >= 2
