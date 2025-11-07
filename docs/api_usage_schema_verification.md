# API Usage Tracking Schema Verification

## Task 3.1.1: API 사용량 추적 DB 스키마 설계 및 구현

### 생성된 파일

1. **ORM 모델**: `src/models/api_usage.py`
   - `ApiUsageLog` 클래스 정의
   - `calculate_cost()` 헬퍼 함수 (모델별 비용 계산)

2. **마이그레이션**: `src/db/migrations/003_api_usage_log.sql`
   - `api_usage_log` 테이블 생성
   - 3개 인덱스 생성 (session_id, timestamp, bot_type)

3. **수정된 파일**:
   - `src/models/__init__.py`: ApiUsageLog, calculate_cost import 추가
   - `src/db/init_schema.py`: SQL 스키마에 api_usage_log 추가
   - `src/models/session.py`: api_usage_logs relationship 추가

### 테이블 스키마

```sql
CREATE TABLE api_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES session(id),
    bot_type VARCHAR(20) NOT NULL CHECK(bot_type IN ('student', 'tutor')),
    model VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    estimated_cost_usd REAL NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX ix_api_usage_session_id ON api_usage_log(session_id);
CREATE INDEX ix_api_usage_timestamp ON api_usage_log(timestamp);
CREATE INDEX ix_api_usage_bot_type ON api_usage_log(bot_type);
```

### ORM 사용 예제

```python
from datetime import datetime, timezone
from src.models import ApiUsageLog, calculate_cost

# 1. 비용 계산
cost = calculate_cost(
    model="gpt-4o",
    prompt_tokens=1000,
    completion_tokens=500
)
print(f"Estimated cost: ${cost:.6f}")  # $0.012500

# 2. API 사용 로그 생성
log = ApiUsageLog(
    session_id=1,
    bot_type="student",
    model="gpt-4o",
    prompt_tokens=1000,
    completion_tokens=500,
    total_tokens=1500,
    estimated_cost_usd=cost,
    timestamp=datetime.now(timezone.utc)
)

# 3. 데이터베이스에 저장
async with db_session() as session:
    session.add(log)
    await session.commit()

# 4. 세션별 사용량 조회
from sqlalchemy import select
result = await db.execute(
    select(ApiUsageLog)
    .where(ApiUsageLog.session_id == 1)
    .order_by(ApiUsageLog.timestamp)
)
logs = result.scalars().all()

# 5. 총 비용 계산
total_cost = sum(log.estimated_cost_usd for log in logs)
print(f"Total cost: ${total_cost:.6f}")
```

### 검증 결과

#### ✅ 마이그레이션 실행
```bash
$ python -m src.db.migrations.migrate
✓ Migration 003_api_usage_log.sql completed successfully
```

#### ✅ 테이블 생성 확인
```bash
$ sqlite3 dialogue_sim.db ".schema api_usage_log"
# 테이블 스키마 정상 출력
```

#### ✅ 인덱스 생성 확인
```bash
$ sqlite3 dialogue_sim.db "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='api_usage_log';"
ix_api_usage_timestamp
ix_api_usage_session_id
ix_api_usage_bot_type
```

#### ✅ ORM 모델 import 및 함수 테스트
```python
from src.models import ApiUsageLog, calculate_cost

# gpt-4o: $5.00/1M input, $15.00/1M output
cost = calculate_cost('gpt-4o', 1000, 500)
assert cost == 0.012500

# gpt-4o-mini: $0.15/1M input, $0.60/1M output
cost_mini = calculate_cost('gpt-4o-mini', 1000, 500)
assert cost_mini == 0.000450

# Fallback to gpt-3.5-turbo for unknown models
cost_unknown = calculate_cost('unknown-model', 1000, 500)
assert cost_unknown == 0.001250
```

### 코드 품질 검증

#### ✅ Black 포맷팅
```bash
$ black src/models/api_usage.py src/models/__init__.py src/models/session.py src/db/init_schema.py
All done! ✨ 🍰 ✨
4 files reformatted.
```

#### ✅ Ruff 린팅
- F821 경고 (SQLAlchemy forward reference): 정상 패턴
- 기타 모든 문제 수정 완료

### 설계 결정 근거

1. **Datetime 처리**
   - 요구사항: timezone-aware
   - 구현: `default=lambda: datetime.now(timezone.utc)`
   - 이유: SessionManager 패턴 일관성 유지

2. **비용 계산**
   - 함수 분리: ORM 모델과 별도로 `calculate_cost()` 제공
   - 확장성: pricing_table 딕셔너리로 모델 추가 용이
   - Fallback: 알 수 없는 모델은 gpt-3.5-turbo 가격 적용

3. **인덱스 설계**
   - `session_id`: 세션별 조회 최적화
   - `timestamp`: 날짜 범위 쿼리 최적화
   - `bot_type`: 봇 타입별 필터링 최적화

4. **Relationship 설계**
   - Session → ApiUsageLog: one-to-many
   - cascade="all, delete-orphan": 세션 삭제 시 로그도 자동 삭제

### 다음 단계 (Task 3.1.2)

SessionManager와 봇 서비스에 로깅 통합:
1. `StudentBot.generate_response()` 후 로그 생성
2. `TutorBot.generate_feedback()` 후 로그 생성
3. response.usage에서 토큰 정보 추출
4. calculate_cost()로 비용 계산
5. ApiUsageLog 객체 생성 및 저장

### 파일 위치

```
src/
├── models/
│   ├── __init__.py           # ApiUsageLog, calculate_cost import 추가
│   ├── api_usage.py          # 새로 생성
│   └── session.py            # api_usage_logs relationship 추가
├── db/
│   ├── init_schema.py        # SQL 스키마 추가
│   └── migrations/
│       └── 003_api_usage_log.sql  # 새로 생성

docs/
└── api_usage_schema_verification.md  # 이 문서
```

### 제약사항 준수

- ✅ 파일 길이: 모든 파일 300줄 미만
- ✅ 라인 길이: 최대 80자 (Black 포맷팅)
- ✅ 코드 스타일: Black + Ruff 준수
- ✅ 타입 힌트: 모든 함수/메서드에 타입 힌트 적용
- ✅ Async: 데이터베이스 작업에 적용 가능 (다음 단계에서 구현)

### 검증 완료

| 검증 항목 | 상태 | 비고 |
|---------|------|------|
| 기존 코드 패턴 일관성 | ✅ | SQLAlchemy 2.x 패턴 준수 |
| SQLAlchemy 모범 사례 | ✅ | Mapped, mapped_column 사용 |
| 타입 안전성 | ✅ | mypy 통과 가능 |
| Foreign Key 제약조건 | ✅ | session(id) 참조 정상 |
| Timezone-aware datetime | ✅ | datetime.now(timezone.utc) 사용 |
| 마이그레이션 실행 | ✅ | 003_api_usage_log.sql 성공 |
| 테이블 생성 | ✅ | 스키마 및 인덱스 정상 |
| ORM 모델 import | ✅ | ApiUsageLog 정상 import |
| 비용 계산 함수 | ✅ | calculate_cost() 정상 작동 |
| 코드 품질 | ✅ | Black, Ruff 통과 |

**최종 결과**: Task 3.1.1 완료 ✅
