#!/usr/bin/env python3
"""
GPT-5 모델 접근 권한 검증 스크립트
실행: python scripts/verify_gpt5_access.py
"""

import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

# .env 파일 로드
load_dotenv()


async def test_gpt5_access():
    """GPT-5 및 대체 모델 접근 권한 테스트"""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    models_to_test = [
        "gpt-5",
        "gpt-5.1-chat-latest",
        "gpt-4-turbo",  # fallback
    ]

    results = []

    for model in models_to_test:
        try:
            response = await client.responses.create(
                model=model,
                input="test",
                max_output_tokens=16,  # 최소값: 16
            )
            results.append(f"✅ {model}: 접근 가능")
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            results.append(f"❌ {model}: {error_type} - {error_msg}")

    return results


if __name__ == "__main__":
    print("=== GPT-5 모델 접근 권한 검증 ===\n")
    results = asyncio.run(test_gpt5_access())
    for result in results:
        print(result)
    print("\n=== 검증 완료 ===")
