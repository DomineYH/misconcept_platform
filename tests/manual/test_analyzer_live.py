"""
Live integration test for Analyzer service.

Calls real OpenAI API to verify analysis functionality.
Run: python -m tests.manual.test_analyzer_live
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, "/mnt/d/dev/misconcept_platform")

# Override reasoning effort for testing (before importing services)
os.environ["ANALYSIS_REASONING"] = "low"  # low for faster/cheaper tests

from src.services.analyzer import Analyzer
from src.models.analysis_framework import AnalysisFramework


class MockFramework:
    """Mock AnalysisFramework for testing."""

    def __init__(self):
        self.name = "Leverage Framework"
        self.description = (
            "분류 체계: 교사 질문을 교육적 효과에 따라 분류"
        )
        self.labels = [
            "Probing",
            "Scaffolding",
            "Direct Instruction",
            "Confirmation",
            "Clarification",
        ]


class TestAnalyzer(Analyzer):
    """Analyzer with higher token limits for testing."""

    def __init__(self):
        super().__init__()
        # Override reasoning effort for testing
        self.reasoning_effort = "low"


async def test_classify_question():
    """Test single question classification with real API."""
    print("\n" + "=" * 60)
    print("🔍 테스트 1: 단일 질문 분류")
    print("=" * 60)

    analyzer = TestAnalyzer()
    framework = MockFramework()

    print(f"   모델: {analyzer.model}")
    print(f"   Reasoning Effort: {analyzer.reasoning_effort}")

    # 테스트 질문
    test_question = "왜 분수의 분모와 분자를 같이 곱해야 한다고 생각하니?"

    # 시나리오 컨텍스트
    scenario_title = "분수의 덧셈 오개념"
    misconception = "분수의 덧셈에서 분모와 분자를 각각 더해야 한다고 생각함"
    student_profile = "초등학교 5학년 학생, 수학에 흥미가 있지만 분수 개념이 약함"

    # 이전 대화 컨텍스트
    context = """teacher: 1/2 + 1/3을 계산해볼까?
student: 2/5요! 분자끼리 더하고 분모끼리 더하면 돼요.
teacher: 흥미로운 답이네. 그렇게 생각한 이유가 뭘까?"""

    print(f"\n📝 질문: {test_question}")
    print(f"📚 시나리오: {scenario_title}")
    print(f"❌ 목표 오개념: {misconception}")
    print(f"👤 학생 프로필: {student_profile}")
    print(f"\n💬 이전 대화:\n{context}")

    try:
        start_time = datetime.now()
        result = await analyzer.classify_question(
            question=test_question,
            framework=framework,
            context=context,
            scenario_title=scenario_title,
            misconception_prompt=misconception,
            student_profile=student_profile,
        )
        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n✅ 분류 완료 ({elapsed:.2f}초)")
        print(f"   라벨: {result['label']}")
        print(f"   신뢰도: {result['confidence']:.2%}")

        reasoning = result.get("reasoning", {})
        if isinstance(reasoning, dict):
            print(f"\n📊 분석 근거:")
            print(f"   요약: {reasoning.get('summary', 'N/A')}")

            if reasoning.get("pedagogical"):
                ped = reasoning["pedagogical"]
                print(f"\n   [교육학적 분석]")
                print(f"   - 교육 원리: {ped.get('educational_principle', 'N/A')}")
                print(f"   - 효과성: {ped.get('effectiveness', 'N/A')}")

            if reasoning.get("cognitive"):
                cog = reasoning["cognitive"]
                print(f"\n   [인지적 분석]")
                print(f"   - 인지적 요구: {cog.get('cognitive_demand', 'N/A')}")
                print(f"   - 오개념 대응: {cog.get('misconception_addressing', 'N/A')}")

            if reasoning.get("contextual"):
                ctx = reasoning["contextual"]
                print(f"\n   [맥락적 분석]")
                print(f"   - 대화 역할: {ctx.get('dialogue_role', 'N/A')}")
                print(f"   - 타이밍: {ctx.get('timing_appropriateness', 'N/A')}")

        return True, result

    except Exception as e:
        print(f"\n❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


async def test_detect_greetings():
    """Test greeting detection with real API."""
    print("\n" + "=" * 60)
    print("👋 테스트 2: 인사말 감지")
    print("=" * 60)

    analyzer = TestAnalyzer()

    print(f"   모델: {analyzer.model}")
    print(f"   Reasoning Effort: {analyzer.reasoning_effort}")

    test_messages = [
        "안녕하세요, 오늘 수업을 시작해볼까요?",
        "분수의 덧셈에 대해 알고 있니?",
        "좋아요, 잘했어요!",
        "1/2 + 1/3의 답이 뭘까?",
        "오늘 수업은 여기까지입니다. 수고했어요!",
    ]

    print("\n📝 테스트 메시지:")
    for i, msg in enumerate(test_messages):
        print(f"   {i}. {msg}")

    try:
        start_time = datetime.now()
        results = await analyzer.detect_greetings(test_messages)
        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n✅ 감지 완료 ({elapsed:.2f}초)")
        print("\n📊 결과:")
        for result in results:
            idx = result["index"]
            is_greeting = result["is_greeting"]
            reason = result.get("reason", "N/A")
            status = "🤝 인사" if is_greeting else "📖 질문"
            print(f"   {idx}. {status} - {reason}")
            print(f"      \"{test_messages[idx][:40]}...\"")

        return True, results

    except Exception as e:
        print(f"\n❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


async def test_batch_classify():
    """Test batch question classification."""
    print("\n" + "=" * 60)
    print("📦 테스트 3: 배치 질문 분류")
    print("=" * 60)

    analyzer = TestAnalyzer()
    framework = MockFramework()

    print(f"   모델: {analyzer.model}")
    print(f"   Reasoning Effort: {analyzer.reasoning_effort}")

    test_questions = [
        "분수의 덧셈에서 분모가 같으면 어떻게 계산하지?",
        "왜 그렇게 생각했니?",
        "1/4 + 1/4는 뭘까?",
    ]

    print("\n📝 테스트 질문:")
    for i, q in enumerate(test_questions):
        print(f"   {i+1}. {q}")

    try:
        start_time = datetime.now()
        results = await analyzer.batch_classify(
            questions=test_questions,
            framework=framework,
            scenario_title="분수 덧셈",
            misconception_prompt="분수 덧셈 시 분모를 더함",
            student_profile="초등학생",
        )
        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n✅ 배치 분류 완료 ({elapsed:.2f}초)")
        print("\n📊 결과:")
        for i, result in enumerate(results):
            print(f"   {i+1}. {result['label']} (신뢰도: {result['confidence']:.2%})")
            if result.get('reasoning', {}).get('summary'):
                print(f"      → {result['reasoning']['summary'][:50]}...")

        return True, results

    except Exception as e:
        print(f"\n❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


async def test_misconception_analyzer():
    """Test MisconceptionAnalyzer with real API."""
    print("\n" + "=" * 60)
    print("🧠 테스트 4: 오개념 분석")
    print("=" * 60)

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from src.services.misconception_analyzer import MisconceptionAnalyzer

    # Create in-memory database session
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as db:
        # Use low reasoning effort for testing
        analyzer = MisconceptionAnalyzer(
            db_session=db,
            reasoning_effort="low"  # Override for testing
        )

        print(f"   모델: {analyzer.model}")
        print(f"   Reasoning Effort: {analyzer.reasoning_effort}")

        # 테스트 데이터
        student_message = "분수를 더할 때는 분자끼리 더하고 분모끼리 더하면 돼요. 1/2 + 1/3 = 2/5예요!"
        scenario_prompt = "분수의 덧셈에서 분모와 분자를 각각 더해야 한다고 잘못 이해함"
        student_profile = "초등학교 5학년, 수학에 자신감이 있지만 분수 개념이 약함"
        scenario_title = "분수 덧셈 오개념 교정"

        print(f"\n💬 학생 응답: {student_message}")
        print(f"❌ 목표 오개념: {scenario_prompt}")

        try:
            start_time = datetime.now()
            result = await analyzer.analyze_student_response(
                student_message=student_message,
                scenario_prompt=scenario_prompt,
                student_profile=student_profile,
                scenario_title=scenario_title,
            )
            elapsed = (datetime.now() - start_time).total_seconds()

            print(f"\n✅ 분석 완료 ({elapsed:.2f}초)")
            print(f"\n📊 분석 결과:")
            print(f"   오개념 유지: {'예' if result['maintains_misconception'] else '아니오'}")
            print(f"   오개념 강도: {result['misconception_strength']:.2%}")
            print(f"   드리프트 감지: {'예' if result['drift_detected'] else '아니오'}")
            print(f"   근거: {result['evidence']}")
            print(f"   분석 노트: {result['analysis_notes']}")

            return True, result

        except Exception as e:
            print(f"\n❌ 오류 발생: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🚀 분석 기능 통합 테스트 시작")
    print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ANALYSIS_REASONING: {os.environ.get('ANALYSIS_REASONING', 'high')}")
    print("=" * 60)

    results = {}

    # Test 1: Single question classification
    success, data = await test_classify_question()
    results["classify_question"] = success

    # Test 2: Greeting detection
    success, data = await test_detect_greetings()
    results["detect_greetings"] = success

    # Test 3: Batch classification
    success, data = await test_batch_classify()
    results["batch_classify"] = success

    # Test 4: Misconception analysis
    success, data = await test_misconception_analyzer()
    results["misconception_analyzer"] = success

    # Summary
    print("\n" + "=" * 60)
    print("📋 테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {name}: {status}")

    print(f"\n   총 결과: {passed}/{total} 통과")

    if passed == total:
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print("\n⚠️ 일부 테스트 실패")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
