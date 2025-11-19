"""OpenAI Responses API 헬퍼 유틸리티."""


def extract_response_text(response) -> str:
    """Responses API 응답에서 텍스트 추출.

    Args:
        response: OpenAI Responses API response 객체

    Returns:
        추출된 텍스트 (빈 문자열 가능)

    Note:
        - response.output은 list[ResponseOutputItem]
        - 각 item.content는 list[ContentBlock]
        - ContentBlock.type == "output_text"인 경우 .text 추출
    """
    text_chunks: list[str] = []

    # response.output 리스트 순회
    for item in getattr(response, "output", []) or []:
        # 각 item의 content 리스트 순회
        for block in getattr(item, "content", []) or []:
            # output_text 타입의 블록에서 text 추출
            if (
                getattr(block, "type", None) == "output_text"
                and hasattr(block, "text")
            ):
                text_chunks.append(block.text)

    # Fallback: response.output_text 속성 확인
    if not text_chunks and hasattr(response, "output_text"):
        raw = response.output_text
        text_chunks.append("".join(raw) if isinstance(raw, list) else raw)

    return "".join(text_chunks).strip()
