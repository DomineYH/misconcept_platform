from typing import Optional
from pydantic import BaseModel, Field

class PromptUpdateRequest(BaseModel):
    """프롬프트 수정 요청 모델."""
    template_name: Optional[str] = Field(None, min_length=3, max_length=100)
    template_text: Optional[str] = Field(None, min_length=10, max_length=10000)

