# 개발자 가이드: 챗봇 구성 시스템

**대상 독자**: 백엔드 개발자, 시스템 아키텍트
**목적**: 챗봇 구성 관리 시스템의 기술적 세부사항 및 확장 방법 제공
**버전**: 1.0 (Phase 2 완료)
**최종 업데이트**: 2025-11-07

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [데이터베이스 스키마](#2-데이터베이스-스키마)
3. [API 엔드포인트](#3-api-엔드포인트)
4. [구성 로딩 메커니즘](#4-구성-로딩-메커니즘)
5. [봇 서비스 통합](#5-봇-서비스-통합)
6. [테스트 가이드](#6-테스트-가이드)
7. [확장 가이드](#7-확장-가이드)
8. [성능 최적화](#8-성능-최적화)

---

## 1. 아키텍처 개요

### 1.1 시스템 구성 요소

챗봇 구성 시스템은 4개의 핵심 레이어로 구성됩니다:

```
┌──────────────────────────────────────────────────┐
│              API Layer                            │
│  - admin_chatbot_config.py (REST API)            │
│  - Pydantic validation                           │
│  - Rate limiting & security                      │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│         Service Layer                             │
│  - config_cache.py (Caching)                     │
│  - session_mgr.py (Config loading)               │
│  - student_bot.py / tutor_bot.py (Consumers)     │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│         Data Layer                                │
│  - chatbot_config (Global settings)              │
│  - chatbot_config_audit (Audit log)              │
│  - scenario (Per-scenario overrides)             │
└───────────────────────────────────────────────────┘
```

### 1.2 데이터 흐름 다이어그램

```
[Admin UI Request]
       │
       ▼
[PUT /admin/chatbot-config] ◄─────── [Pydantic Validation]
       │
       ├──► [Load Current Config] ──► [BotConfigCache]
       │
       ├──► [Update Database Records]
       │         │
       │         ├──► [chatbot_config table]
       │         └──► [chatbot_config_audit table]
       │
       └──► [Invalidate Cache] ──► [BotConfigCache.invalidate()]


[Session Start]
       │
       ▼
[SessionManager.initialize()]
       │
       ├──► [Load Scenario from DB]
       │
       ├──► [_load_bot_config(scenario)]
       │         │
       │         ├──► [BotConfigCache.get_global_config()] ← (5-min TTL)
       │         │
       │         └──► [Apply Priority Chain]
       │                   │
       │                   ├─► 1. Scenario Override
       │                   ├─► 2. Global DB Config
       │                   ├─► 3. Environment Variables
       │                   └─► 4. Hardcoded Defaults
       │
       ├──► [Initialize StudentBot(config)]
       │
       └──► [Initialize TutorBot(config) if enabled]
```

### 1.3 구성 우선순위 체인

설정은 다음 우선순위로 적용됩니다 (높은 순서부터):

```python
# Priority 1: Scenario-specific override (최우선)
scenario.chat_model = "gpt-3.5-turbo"

# Priority 2: Global database configuration
chatbot_config.student_bot.model = "gpt-4-turbo"

# Priority 3: Environment variables (.env)
CHAT_MODEL = "gpt-3.5-turbo"

# Priority 4: Hardcoded defaults (코드 내 기본값)
DEFAULT_MODEL = "gpt-4-turbo"
```

**결정 로직 (코드 예시)**:

```python
student_model = (
    scenario.chat_model  # Scenario override
    or db_config.get("student_bot.model")  # Global DB
    or config.CHAT_MODEL  # Env variable
)
```

---

## 2. 데이터베이스 스키마

### 2.1 chatbot_config 테이블

**목적**: 전역 챗봇 설정 저장

```sql
CREATE TABLE chatbot_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) NOT NULL
        CHECK(config_type IN ('string', 'float', 'int', 'bool')),
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES user(id)
);

CREATE INDEX idx_chatbot_config_key ON chatbot_config(config_key);
```

**주요 설정 키**:

| config_key | config_value | config_type | 설명 |
|-----------|-------------|------------|------|
| `student_bot.model` | `gpt-4-turbo` | string | StudentBot LLM 모델 |
| `student_bot.temperature` | `0.7` | float | 응답 창의성 (0.0-2.0) |
| `student_bot.max_tokens` | `150` | int | 응답 길이 제한 |
| `tutor_bot.model` | `gpt-3.5-turbo` | string | TutorBot LLM 모델 |
| `tutor_bot.temperature` | `0.3` | float | 응답 일관성 (0.0-2.0) |
| `tutor_bot.max_tokens` | `100` | int | 응답 길이 제한 |
| `tutor_bot.intervention_threshold` | `3` | int | 10개 질문당 개입 횟수 |

**ORM 모델 (SQLAlchemy)**:

```python
class ChatbotConfig(Base):
    __tablename__ = "chatbot_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"))

    updater: Mapped[Optional["User"]] = relationship("User", back_populates="config_updates")
```

### 2.2 chatbot_config_audit 테이블

**목적**: 구성 변경 감사 로그

```sql
CREATE TABLE chatbot_config_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    changed_by INTEGER NOT NULL REFERENCES user(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

CREATE INDEX idx_chatbot_audit_key ON chatbot_config_audit(config_key);
CREATE INDEX idx_chatbot_audit_timestamp ON chatbot_config_audit(changed_at);
```

**감사 로그 예시**:

| config_key | old_value | new_value | changed_by | changed_at | ip_address |
|-----------|----------|-----------|-----------|-----------|-----------|
| `student_bot.temperature` | `0.7` | `0.9` | 1 | 2025-11-07 10:30:15 | 192.168.1.100 |
| `tutor_bot.model` | `gpt-3.5-turbo` | `gpt-4-turbo` | 1 | 2025-11-07 10:32:45 | 192.168.1.100 |

**ORM 모델**:

```python
class ChatbotConfigAudit(Base):
    __tablename__ = "chatbot_config_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    user: Mapped["User"] = relationship("User")
```

### 2.3 scenario 테이블 확장 (4개 컬럼 추가)

**Phase 2 확장**: 시나리오별 봇 설정 오버라이드

```sql
-- 기존 scenario 테이블에 4개 컬럼 추가
ALTER TABLE scenario ADD COLUMN chat_model VARCHAR(50) NULL;
ALTER TABLE scenario ADD COLUMN chat_temperature REAL NULL
    CHECK (chat_temperature IS NULL OR (chat_temperature >= 0 AND chat_temperature <= 2));
ALTER TABLE scenario ADD COLUMN tutor_enabled BOOLEAN NOT NULL DEFAULT 1;
ALTER TABLE scenario ADD COLUMN tutor_intervention_threshold INTEGER NULL
    CHECK (tutor_intervention_threshold IS NULL OR (tutor_intervention_threshold BETWEEN 1 AND 10));
```

**컬럼 의미**:

| 컬럼명 | 타입 | NULL 허용 | 설명 |
|-------|------|---------|------|
| `chat_model` | VARCHAR(50) | ✅ | StudentBot 모델 오버라이드 (NULL = 전역 설정 사용) |
| `chat_temperature` | REAL | ✅ | Temperature 오버라이드 (NULL = 전역 설정 사용) |
| `tutor_enabled` | BOOLEAN | ❌ | TutorBot 활성화 여부 (기본: 1) |
| `tutor_intervention_threshold` | INTEGER | ✅ | TutorBot 개입 빈도 오버라이드 (NULL = 전역 설정 사용) |

**ORM 모델 확장**:

```python
class Scenario(Base):
    __tablename__ = "scenario"

    # ... 기존 필드 ...

    # Phase 2: Scenario-specific chatbot configuration override
    chat_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Override StudentBot model for this scenario (NULL = use global)",
    )

    chat_temperature: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Override temperature 0.0-2.0 (NULL = use global)",
    )

    tutor_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable/disable TutorBot for this scenario",
    )

    tutor_intervention_threshold: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Override tutor interventions per 10 questions (NULL = use global)",
    )
```

### 2.4 마이그레이션 스크립트

**파일**: `src/db/migrations/001_add_chatbot_config.sql`

```sql
-- Phase 1: Global configuration tables
CREATE TABLE IF NOT EXISTS chatbot_config (...);
CREATE TABLE IF NOT EXISTS chatbot_config_audit (...);

-- Seed default values
INSERT INTO chatbot_config (config_key, config_value, config_type, description) VALUES
('student_bot.model', 'gpt-4-turbo', 'string', 'StudentBot LLM model'),
('student_bot.temperature', '0.7', 'float', 'StudentBot response creativity (0.0-2.0)'),
-- ... (7 rows total)
```

**파일**: `src/db/migrations/002_scenario_bot_config.sql`

```sql
-- Phase 2: Scenario-level overrides
ALTER TABLE scenario ADD COLUMN chat_model VARCHAR(50) NULL;
ALTER TABLE scenario ADD COLUMN chat_temperature REAL NULL
    CHECK (chat_temperature IS NULL OR (chat_temperature >= 0 AND chat_temperature <= 2));
ALTER TABLE scenario ADD COLUMN tutor_enabled BOOLEAN NOT NULL DEFAULT 1;
ALTER TABLE scenario ADD COLUMN tutor_intervention_threshold INTEGER NULL
    CHECK (tutor_intervention_threshold IS NULL OR (tutor_intervention_threshold BETWEEN 1 AND 10));
```

**마이그레이션 실행**:

```bash
# 마이그레이션은 seed.py에서 자동 실행됨
python -m src.db.seed

# 또는 SQL 파일 직접 실행
sqlite3 dialogue_sim.db < src/db/migrations/001_add_chatbot_config.sql
sqlite3 dialogue_sim.db < src/db/migrations/002_scenario_bot_config.sql
```

---

## 3. API 엔드포인트

### 3.1 GET /admin/chatbot-config

**목적**: 현재 챗봇 전역 설정 조회

**보안**:
- 관리자 권한 필요
- Rate limit: 30 requests/minute

**요청 예시**:

```bash
curl -X GET http://localhost:8000/admin/chatbot-config \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

**응답 예시**:

```json
{
  "student_bot": {
    "model": "gpt-4-turbo",
    "temperature": 0.7,
    "max_tokens": 150
  },
  "tutor_bot": {
    "model": "gpt-3.5-turbo",
    "temperature": 0.3,
    "max_tokens": 100,
    "intervention_threshold": 3
  }
}
```

**코드 구현**:

```python
@router.get("/", response_model=BotConfigResponse)
async def get_chatbot_config(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Retrieve current chatbot configuration."""
    _check_admin_role(user)

    # Load config using cache (<10ms)
    configs = await _get_current_config(db)

    return BotConfigResponse(
        student_bot={
            "model": configs.get("student_bot.model", config.CHAT_MODEL),
            "temperature": float(configs.get("student_bot.temperature", "0.7")),
            "max_tokens": int(configs.get("student_bot.max_tokens", "150")),
        },
        tutor_bot={
            "model": configs.get("tutor_bot.model", config.ANALYSIS_MODEL),
            "temperature": float(configs.get("tutor_bot.temperature", "0.3")),
            "max_tokens": int(configs.get("tutor_bot.max_tokens", "100")),
            "intervention_threshold": int(configs.get("tutor_bot.intervention_threshold", "3")),
        },
    )
```

### 3.2 PUT /admin/chatbot-config

**목적**: 챗봇 전역 설정 업데이트

**보안**:
- 관리자 권한 필요
- Rate limit: 10 requests/minute
- 모든 변경사항 감사 로그 기록

**요청 예시**:

```bash
curl -X PUT http://localhost:8000/admin/chatbot-config \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "student_bot_model": "gpt-3.5-turbo",
    "student_bot_temperature": 0.8,
    "student_bot_max_tokens": 200,
    "tutor_bot_model": "gpt-3.5-turbo",
    "tutor_bot_temperature": 0.3,
    "tutor_bot_max_tokens": 100,
    "tutor_bot_intervention_threshold": 5
  }'
```

**Pydantic 검증 규칙**:

```python
class BotConfigUpdate(BaseModel):
    """Chatbot configuration update payload with validation."""

    student_bot_model: str = Field(
        ...,
        pattern=r"^gpt-(3\.5|4)-turbo$",
        description="Must be gpt-3.5-turbo or gpt-4-turbo",
    )
    student_bot_temperature: float = Field(
        ..., ge=0.0, le=2.0, description="Temperature between 0.0 and 2.0"
    )
    student_bot_max_tokens: int = Field(
        ..., ge=50, le=500, description="Max tokens between 50 and 500"
    )
    tutor_bot_model: str = Field(
        ...,
        pattern=r"^gpt-(3\.5|4)-turbo$",
        description="Must be gpt-3.5-turbo or gpt-4-turbo",
    )
    tutor_bot_temperature: float = Field(
        ..., ge=0.0, le=2.0, description="Temperature between 0.0 and 2.0"
    )
    tutor_bot_max_tokens: int = Field(
        ..., ge=50, le=300, description="Max tokens between 50 and 300"
    )
    tutor_bot_intervention_threshold: int = Field(
        ..., ge=1, le=10, description="Interventions per 10 questions (1-10)"
    )

    @field_validator("student_bot_model", "tutor_bot_model")
    @classmethod
    def validate_model_availability(cls, v):
        """Validate model is in allowed list."""
        allowed_models = ["gpt-4-turbo", "gpt-3.5-turbo"]
        if v not in allowed_models:
            raise ValueError(
                f"Model '{v}' not allowed. Use: {', '.join(allowed_models)}"
            )
        return v
```

**검증 에러 예시**:

```json
{
  "detail": [
    {
      "type": "float_parsing",
      "loc": ["body", "student_bot_temperature"],
      "msg": "Input should be a valid number, got 'abc'",
      "input": "abc"
    },
    {
      "type": "greater_than_equal",
      "loc": ["body", "student_bot_max_tokens"],
      "msg": "Input should be greater than or equal to 50",
      "input": 30
    }
  ]
}
```

**응답 예시**:

```json
{
  "message": "Chatbot configuration updated successfully"
}
```

**구현 로직**:

```python
@router.put("/")
@limiter.limit("10/minute")
async def update_chatbot_config(
    request: Request,
    config_update: BotConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Update chatbot configuration."""
    _check_admin_role(user)

    # Get current config for audit log
    current_config = await _get_current_config(db)

    # Prepare updates
    updates = {
        "student_bot.model": config_update.student_bot_model,
        "student_bot.temperature": str(config_update.student_bot_temperature),
        "student_bot.max_tokens": str(config_update.student_bot_max_tokens),
        # ... (7 total updates)
    }

    # Update database and log audit trail
    for key, new_value in updates.items():
        result = await db.execute(
            select(ChatbotConfig).where(ChatbotConfig.config_key == key)
        )
        config_row = result.scalar_one_or_none()

        old_value = current_config.get(key)

        if config_row:
            config_row.config_value = new_value
            config_row.updated_at = datetime.now(timezone.utc)
            config_row.updated_by = user.id

        # Log audit trail
        await _log_config_audit(db, user, request, key, old_value, new_value)

    await db.commit()

    # Invalidate cache so new sessions use updated config
    await bot_config_cache.invalidate()

    return {"message": "Chatbot configuration updated successfully"}
```

### 3.3 GET /admin/chatbot-config/costs

**목적**: API 사용량 및 비용 메트릭 조회 (Phase 3 구현 예정)

**현재 상태**: 플레이스홀더 (OpenAI 대시보드 참조 안내)

**요청 예시**:

```bash
curl -X GET "http://localhost:8000/admin/chatbot-config/costs?days=7" \
  -H "Authorization: Bearer {admin_token}"
```

**현재 응답**:

```json
{
  "message": "Cost tracking will be implemented in Phase 3. Please monitor OpenAI dashboard for usage.",
  "placeholder": true
}
```

**Phase 3 계획 응답** (미래):

```json
{
  "date_range": {
    "start": "2025-11-01",
    "end": "2025-11-07"
  },
  "total_api_calls": 1234,
  "total_tokens": 456789,
  "estimated_cost": 12.34,
  "usage_by_model": {
    "gpt-4-turbo": {
      "calls": 234,
      "tokens": 123456,
      "cost": 10.50
    },
    "gpt-3.5-turbo": {
      "calls": 1000,
      "tokens": 333333,
      "cost": 1.84
    }
  },
  "usage_by_bot_type": {
    "student": {
      "calls": 617,
      "cost": 8.20
    },
    "tutor": {
      "calls": 617,
      "cost": 4.14
    }
  },
  "top_scenarios_by_cost": [
    {
      "scenario_id": 1,
      "scenario_title": "Complex Math Misconception",
      "cost": 3.45
    }
  ]
}
```

### 3.4 POST /admin/chatbot-config/reset

**목적**: 모든 설정을 공장 초기화

**보안**:
- 관리자 권한 필요
- Rate limit: 5 requests/minute
- 모든 리셋 감사 로그 기록

**요청 예시**:

```bash
curl -X POST http://localhost:8000/admin/chatbot-config/reset \
  -H "Authorization: Bearer {admin_token}"
```

**응답 예시**:

```json
{
  "message": "Configuration reset to defaults",
  "defaults": {
    "student_bot": {
      "model": "gpt-4-turbo",
      "temperature": 0.7,
      "max_tokens": 150
    },
    "tutor_bot": {
      "model": "gpt-3.5-turbo",
      "temperature": 0.3,
      "max_tokens": 100,
      "intervention_threshold": 3
    }
  }
}
```

### 3.5 Rate Limiting 설정

**구현 도구**: `slowapi` (Flask-Limiter 포트)

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, enabled=not config.TESTING)

# 엔드포인트별 제한
@router.get("/")  # 30 requests/minute (기본값)
@router.put("/")
@limiter.limit("10/minute")  # 10 requests/minute
@router.post("/reset")
@limiter.limit("5/minute")  # 5 requests/minute
```

**Rate Limit 초과 시 응답**:

```json
{
  "error": "Rate limit exceeded: 10 per 1 minute"
}
```

---

## 4. 구성 로딩 메커니즘

### 4.1 SessionManager._load_bot_config() 로직

**파일**: `src/services/session_mgr.py`

**목적**: 세션 시작 시 봇 구성을 우선순위에 따라 로드

**코드 구현**:

```python
async def _load_bot_config(self, scenario: Scenario) -> dict:
    """Load bot config: Scenario > Global > Env > Default.

    Configuration priority:
    1. Scenario-specific overrides (highest priority)
    2. Global chatbot_config table
    3. Environment variables (fallback)
    4. Hardcoded defaults

    Args:
        scenario: Scenario model with optional bot config overrides

    Returns:
        Dictionary with complete bot configuration parameters
    """
    # Load global config from database using cache (<10ms)
    db_config = await bot_config_cache.get_global_config(self.db)

    # Apply scenario-specific overrides with proper priority
    return {
        # StudentBot configuration
        "student_model": (
            scenario.chat_model  # Priority 1: Scenario override
            or db_config.get("student_bot.model")  # Priority 2: Global DB
            or config.CHAT_MODEL  # Priority 3: Env variable
        ),
        "student_temperature": (
            scenario.chat_temperature  # Scenario override (can be 0.0)
            if scenario.chat_temperature is not None
            else float(db_config.get("student_bot.temperature", "0.7"))
        ),
        "student_max_tokens": int(
            db_config.get("student_bot.max_tokens", "150")
        ),

        # TutorBot configuration
        "tutor_enabled": scenario.tutor_enabled,  # NOT NULL
        "tutor_model": db_config.get(
            "tutor_bot.model", config.ANALYSIS_MODEL
        ),
        "tutor_temperature": float(
            db_config.get("tutor_bot.temperature", "0.3")
        ),
        "tutor_max_tokens": int(
            db_config.get("tutor_bot.max_tokens", "100")
        ),
        "tutor_intervention_threshold": (
            scenario.tutor_intervention_threshold  # Scenario override
            if scenario.tutor_intervention_threshold is not None
            else int(db_config.get("tutor_bot.intervention_threshold", "3"))
        ),
    }
```

### 4.2 우선순위 적용 예시

**시나리오**:

```python
# Scenario 테이블
scenario = Scenario(
    id=1,
    title="Photosynthesis Misconception",
    chat_model="gpt-3.5-turbo",  # 오버라이드
    chat_temperature=None,  # 전역 설정 사용
    tutor_enabled=False,  # TutorBot 비활성화
    tutor_intervention_threshold=None,
)

# chatbot_config 테이블
db_config = {
    "student_bot.model": "gpt-4-turbo",
    "student_bot.temperature": "0.7",
    "student_bot.max_tokens": "150",
    "tutor_bot.model": "gpt-3.5-turbo",
    "tutor_bot.intervention_threshold": "3",
}

# config.py (환경 변수)
config.CHAT_MODEL = "gpt-3.5-turbo"
config.ANALYSIS_MODEL = "gpt-4-turbo"
```

**결과**:

```python
{
    "student_model": "gpt-3.5-turbo",  # Scenario override
    "student_temperature": 0.7,  # Global DB (scenario=NULL)
    "student_max_tokens": 150,  # Global DB
    "tutor_enabled": False,  # Scenario (TutorBot OFF)
    "tutor_model": "gpt-3.5-turbo",  # Global DB (but unused)
    "tutor_temperature": 0.3,  # Global DB
    "tutor_max_tokens": 100,  # Global DB
    "tutor_intervention_threshold": 3,  # Global DB (but unused)
}
```

### 4.3 캐싱 시스템 (`config_cache.py`)

**파일**: `src/services/config_cache.py`

**목적**: 데이터베이스 쿼리 최소화 및 <10ms 응답 시간 달성

**핵심 기능**:

```python
class BotConfigCache:
    """In-memory cache for bot configuration with TTL and invalidation."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize config cache.

        Args:
            ttl_seconds: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: Dict[str, Tuple[dict, datetime]] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def get_global_config(self, db: AsyncSession) -> dict:
        """Get global bot config with caching.

        Performance target: <10ms (cache hit), <50ms (cache miss)
        """
        cache_key = "global_config"

        # Thread-safe cache access
        async with self._lock:
            # Check cache
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if datetime.now(timezone.utc) - timestamp < timedelta(seconds=self._ttl):
                    return cached_data  # Cache hit

        # Cache miss - load from DB
        result = await db.execute(select(ChatbotConfig))
        configs = {
            row.config_key: row.config_value
            for row in result.scalars().all()
        }

        # Update cache
        async with self._lock:
            self._cache[cache_key] = (configs, datetime.now(timezone.utc))

        return configs

    async def invalidate(self) -> None:
        """Clear cache when configuration is updated."""
        async with self._lock:
            self._cache.clear()
```

**성능 메트릭**:

| 상황 | 응답 시간 | DB 쿼리 |
|-----|---------|--------|
| Cache hit (5분 이내) | <10ms | 0 |
| Cache miss (첫 요청) | <50ms | 1 |
| Invalidation 후 | <50ms | 1 |

### 4.4 캐시 무효화 전략

**자동 무효화 트리거**:

1. **전역 설정 업데이트**:
   ```python
   # PUT /admin/chatbot-config 완료 후
   await bot_config_cache.invalidate()
   ```

2. **설정 리셋**:
   ```python
   # POST /admin/chatbot-config/reset 완료 후
   await bot_config_cache.invalidate()
   ```

3. **TTL 만료**:
   - 5분 경과 시 자동 만료
   - 다음 요청 시 DB에서 재로드

**수동 무효화** (개발자 콘솔):

```python
from src.services.config_cache import bot_config_cache

# 전역 캐시 무효화
await bot_config_cache.invalidate()

# 특정 시나리오 캐시 무효화 (Phase 2)
await bot_config_cache.invalidate_scenario(scenario_id=1)
```

---

## 5. 봇 서비스 통합

### 5.1 StudentBot.__init__() 매개변수

**파일**: `src/services/student_bot.py`

**구성 매개변수 전달**:

```python
class StudentBot:
    """AI-powered student simulation with configurable parameters."""

    def __init__(
        self,
        scenario_prompt: str,
        scenario_title: str,
        student_profile: str,
        model: str = "gpt-4-turbo",  # 동적으로 전달됨
        temperature: float = 0.7,  # 동적으로 전달됨
        max_tokens: int = 150,  # 동적으로 전달됨
    ):
        """Initialize StudentBot with scenario context and configuration.

        Args:
            scenario_prompt: System prompt defining the misconception
            scenario_title: Scenario title for context
            student_profile: Student characteristics (e.g., "Grade 5 student")
            model: OpenAI model name (from config system)
            temperature: Response creativity (0.0-2.0, from config system)
            max_tokens: Response length limit (from config system)
        """
        self.scenario_prompt = scenario_prompt
        self.scenario_title = scenario_title
        self.student_profile = student_profile
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
```

**SessionManager에서 호출**:

```python
# SessionManager.initialize()
bot_config = await self._load_bot_config(scenario)

self.student_bot = StudentBot(
    scenario_prompt=scenario.prompt,
    scenario_title=scenario.title,
    student_profile=scenario.student_profile or "Grade 5 student",
    model=bot_config["student_model"],  # 구성 시스템에서 로드
    temperature=bot_config["student_temperature"],
    max_tokens=bot_config["student_max_tokens"],
)
```

### 5.2 TutorBot.__init__() 매개변수

**파일**: `src/services/tutor_bot.py`

**구성 매개변수 전달**:

```python
class TutorBot:
    """AI-powered pedagogical feedback system with configurable behavior."""

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",  # 동적으로 전달됨
        temperature: float = 0.3,  # 동적으로 전달됨
        max_tokens: int = 100,  # 동적으로 전달됨
        intervention_threshold: int = 3,  # 동적으로 전달됨
    ):
        """Initialize TutorBot with configuration.

        Args:
            model: OpenAI model name (from config system)
            temperature: Response consistency (0.0-2.0, from config system)
            max_tokens: Response length limit (from config system)
            intervention_threshold: Interventions per 10 teacher questions
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.intervention_threshold = intervention_threshold
        self.question_count = 0
        self.client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    async def generate_feedback(
        self,
        teacher_content: str,
        student_content: str,
        history: list[dict],
    ) -> str | None:
        """Generate pedagogical feedback if intervention threshold met.

        Returns:
            Feedback content or None if threshold not met
        """
        self.question_count += 1

        # Intervention probability: threshold / 10
        # e.g., threshold=3 → 30% chance per question
        intervention_probability = self.intervention_threshold / 10

        if random.random() > intervention_probability:
            return None  # No intervention

        # Generate feedback using configured model and parameters
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[...],
        )

        return response.choices[0].message.content
```

### 5.3 조건부 TutorBot 초기화

**시나리오별 TutorBot 활성화/비활성화**:

```python
# SessionManager.initialize()
bot_config = await self._load_bot_config(scenario)

# Conditionally initialize TutorBot based on scenario setting
if bot_config["tutor_enabled"]:
    self.tutor_bot = TutorBot(
        model=bot_config["tutor_model"],
        temperature=bot_config["tutor_temperature"],
        max_tokens=bot_config["tutor_max_tokens"],
        intervention_threshold=bot_config["tutor_intervention_threshold"],
    )
else:
    self.tutor_bot = None  # TutorBot disabled for this scenario
```

**메시지 처리 시 체크**:

```python
# SessionManager.process_teacher_message()
async def process_teacher_message(self, teacher_content: str) -> list[Message]:
    # ... StudentBot 응답 생성 ...

    # Check if tutor should intervene (only if enabled)
    if self.tutor_bot:  # None 체크
        tutor_feedback = await self.tutor_bot.generate_feedback(
            teacher_content, student_content, history
        )

        if tutor_feedback:
            tutor_msg = Message(
                session_id=self.session_id,
                role="tutor",
                content=tutor_feedback,
            )
            self.db.add(tutor_msg)
            new_messages.append(tutor_msg)

    return new_messages
```

---

## 6. 테스트 가이드

### 6.1 단위 테스트 작성 방법

**파일**: `tests/unit/test_config_cache.py`

**테스트 구조**:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.config_cache import BotConfigCache
from src.models.chatbot_config import ChatbotConfig

class TestBotConfigCache:
    """Test configuration caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_miss_loads_from_db(self):
        """Test that cache miss loads configuration from database."""
        # Arrange: Create mock database session
        db_mock = AsyncMock()
        result_mock = MagicMock()

        config_row = MagicMock(spec=ChatbotConfig)
        config_row.config_key = "student_bot.model"
        config_row.config_value = "gpt-4-turbo"

        result_mock.scalars.return_value.all.return_value = [config_row]
        db_mock.execute.return_value = result_mock

        cache = BotConfigCache(ttl_seconds=300)

        # Act: First call should be cache miss
        config = await cache.get_global_config(db_mock)

        # Assert: DB was queried
        assert db_mock.execute.called
        assert config["student_bot.model"] == "gpt-4-turbo"

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self):
        """Test that subsequent calls use cached data without DB query."""
        # ... (mock setup) ...

        # Act
        config1 = await cache.get_global_config(db_mock)
        first_call_count = db_mock.execute.call_count

        config2 = await cache.get_global_config(db_mock)
        second_call_count = db_mock.execute.call_count

        # Assert: DB only called once (cache hit on second call)
        assert second_call_count == first_call_count
        assert config1 == config2
```

**실행**:

```bash
pytest tests/unit/test_config_cache.py -v
```

### 6.2 통합 테스트 예시

**파일**: `tests/integration/test_admin_chatbot_config.py`

**API 엔드포인트 테스트**:

```python
import pytest
from httpx import AsyncClient
from src.main import app

class TestAdminChatbotConfig:
    """Integration tests for chatbot configuration API."""

    @pytest.mark.asyncio
    async def test_get_config_returns_current_settings(
        self, async_client: AsyncClient, admin_token: str
    ):
        """Test GET /admin/chatbot-config returns current configuration."""
        # Act
        response = await async_client.get(
            "/admin/chatbot-config",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "student_bot" in data
        assert "tutor_bot" in data
        assert data["student_bot"]["model"] in ["gpt-4-turbo", "gpt-3.5-turbo"]

    @pytest.mark.asyncio
    async def test_update_config_validates_input(
        self, async_client: AsyncClient, admin_token: str
    ):
        """Test PUT /admin/chatbot-config validates input parameters."""
        # Arrange: Invalid temperature (> 2.0)
        invalid_payload = {
            "student_bot_model": "gpt-4-turbo",
            "student_bot_temperature": 3.0,  # Invalid
            "student_bot_max_tokens": 150,
            "tutor_bot_model": "gpt-3.5-turbo",
            "tutor_bot_temperature": 0.3,
            "tutor_bot_max_tokens": 100,
            "tutor_bot_intervention_threshold": 3,
        }

        # Act
        response = await async_client.put(
            "/admin/chatbot-config",
            json=invalid_payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Assert: Validation error
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("temperature" in err["loc"] for err in errors)
```

**실행**:

```bash
pytest tests/integration/test_admin_chatbot_config.py -v
```

### 6.3 Fixtures 사용법

**파일**: `tests/conftest.py`

**공통 Fixtures 정의**:

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.main import app
from src.db.connection import get_db_session

@pytest.fixture
async def async_client():
    """Provide async HTTP client for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def db_session():
    """Provide test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
def admin_token(db_session):
    """Provide admin authentication token."""
    # Create admin user and generate JWT token
    admin_user = User(email="admin@test.com", role="admin")
    db_session.add(admin_user)
    await db_session.commit()

    token = create_access_token(data={"sub": admin_user.email})
    return token
```

**Fixture 사용 예시**:

```python
@pytest.mark.asyncio
async def test_update_config_as_admin(
    async_client: AsyncClient,  # Fixture 주입
    admin_token: str,  # Fixture 주입
    db_session: AsyncSession,  # Fixture 주입
):
    """Test that admin can update configuration."""
    # async_client, admin_token, db_session 모두 자동으로 제공됨
    response = await async_client.put(
        "/admin/chatbot-config",
        json={...},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
```

### 6.4 E2E 테스트 (시나리오 오버라이드)

**파일**: `tests/integration/test_scenario_bot_override_e2e.py`

**전체 워크플로우 테스트**:

```python
@pytest.mark.asyncio
async def test_scenario_override_affects_bot_behavior(
    async_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
):
    """Test that scenario-level overrides actually affect bot responses."""

    # 1. Create scenario with custom bot config
    scenario_payload = {
        "title": "Test Scenario",
        "prompt": "Student believes photosynthesis creates oxygen from CO2",
        "student_profile": "Grade 5",
        "framework_id": 1,
        "use_custom_bot_config": True,
        "chat_model": "gpt-3.5-turbo",  # Override
        "chat_temperature": 0.9,  # Override
        "tutor_enabled": False,  # Disable TutorBot
    }

    response = await async_client.post(
        "/admin/scenarios",
        json=scenario_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    scenario_id = response.json()["id"]

    # 2. Start session with this scenario
    session_response = await async_client.post(
        "/sessions/start",
        json={"scenario_id": scenario_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    session_id = session_response.json()["id"]

    # 3. Send teacher message
    message_response = await async_client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "What is photosynthesis?"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    messages = message_response.json()["messages"]

    # 4. Verify bot behavior
    assert len(messages) == 2  # Teacher + Student (no Tutor)
    assert messages[0]["role"] == "teacher"
    assert messages[1]["role"] == "student"
    # No tutor message because tutor_enabled=False

    # 5. Verify model used (check logs or metadata)
    # This would require additional instrumentation in StudentBot
```

---

## 7. 확장 가이드

### 7.1 새로운 봇 매개변수 추가 방법

**예시**: `student_bot_system_message_prefix` 추가

#### Step 1: 데이터베이스 마이그레이션

```sql
-- src/db/migrations/003_add_system_message_prefix.sql
INSERT INTO chatbot_config (config_key, config_value, config_type, description) VALUES
('student_bot.system_message_prefix', 'You are a student who...', 'string', 'Custom system message prefix for StudentBot');
```

#### Step 2: Pydantic 스키마 업데이트

```python
# src/api/routes/admin_chatbot_config.py
class BotConfigUpdate(BaseModel):
    # ... 기존 필드 ...

    student_bot_system_message_prefix: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Custom system message prefix (10-500 characters)",
    )
```

#### Step 3: SessionManager 로딩 로직 수정

```python
# src/services/session_mgr.py
async def _load_bot_config(self, scenario: Scenario) -> dict:
    db_config = await bot_config_cache.get_global_config(self.db)

    return {
        # ... 기존 설정 ...
        "student_system_message_prefix": db_config.get(
            "student_bot.system_message_prefix",
            "You are a helpful student assistant."
        ),
    }
```

#### Step 4: StudentBot 수정

```python
# src/services/student_bot.py
class StudentBot:
    def __init__(
        self,
        # ... 기존 매개변수 ...
        system_message_prefix: str = "You are a helpful student assistant.",
    ):
        self.system_message_prefix = system_message_prefix

    async def generate_response(self, teacher_content: str, history: list[dict]) -> str:
        system_message = f"{self.system_message_prefix}\n\n{self.scenario_prompt}"
        # ... 나머지 로직 ...
```

#### Step 5: 테스트 작성

```python
# tests/integration/test_system_message_prefix.py
@pytest.mark.asyncio
async def test_custom_system_message_prefix(async_client, admin_token):
    # Update config
    response = await async_client.put(
        "/admin/chatbot-config",
        json={
            # ... 기존 필드 ...
            "student_bot_system_message_prefix": "Custom prefix here",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    # Verify it's used in session
    # ... (세션 시작 및 검증) ...
```

### 7.2 새로운 엔드포인트 추가 절차

**예시**: `GET /admin/chatbot-config/history` (구성 변경 이력)

#### Step 1: 라우터에 엔드포인트 추가

```python
# src/api/routes/admin_chatbot_config.py
@router.get("/history")
async def get_config_history(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    limit: int = 50,
):
    """Get configuration change history from audit log.

    Args:
        db: Database session
        user: Current user
        limit: Number of recent changes to return (default: 50)

    Returns:
        List of audit log entries
    """
    _check_admin_role(user)

    result = await db.execute(
        select(ChatbotConfigAudit)
        .order_by(ChatbotConfigAudit.changed_at.desc())
        .limit(limit)
    )
    audit_entries = result.scalars().all()

    return {
        "history": [
            {
                "config_key": entry.config_key,
                "old_value": entry.old_value,
                "new_value": entry.new_value,
                "changed_by": entry.changed_by,
                "changed_at": entry.changed_at.isoformat(),
                "ip_address": entry.ip_address,
            }
            for entry in audit_entries
        ]
    }
```

#### Step 2: Pydantic 응답 스키마 정의

```python
class ConfigAuditEntry(BaseModel):
    config_key: str
    old_value: str | None
    new_value: str
    changed_by: int
    changed_at: str
    ip_address: str | None

class ConfigHistoryResponse(BaseModel):
    history: list[ConfigAuditEntry]
```

#### Step 3: 테스트 작성

```python
@pytest.mark.asyncio
async def test_get_config_history(async_client, admin_token):
    response = await async_client.get(
        "/admin/chatbot-config/history?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert isinstance(data["history"], list)
```

### 7.3 Phase 3 기능 구현 로드맵

**Phase 3 목표**: 비용 추적 및 분석 기능 구현

#### 기능 1: API 사용량 추적

**새 테이블 생성**:

```sql
-- src/db/migrations/004_add_api_usage_tracking.sql
CREATE TABLE api_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES session(id),
    bot_type VARCHAR(20) NOT NULL CHECK(bot_type IN ('student', 'tutor')),
    model VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    estimated_cost REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_usage_session ON api_usage_log(session_id);
CREATE INDEX idx_api_usage_timestamp ON api_usage_log(created_at);
CREATE INDEX idx_api_usage_model ON api_usage_log(model);
```

**ORM 모델**:

```python
class APIUsageLog(Base):
    __tablename__ = "api_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("session.id"))
    bot_type: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

#### 기능 2: 비용 계산 로직

```python
# src/services/cost_calculator.py
class CostCalculator:
    """Calculate OpenAI API costs based on model and token usage."""

    # Pricing (as of 2024, USD per 1K tokens)
    PRICING = {
        "gpt-4-turbo": {
            "input": 0.01,
            "output": 0.03,
        },
        "gpt-3.5-turbo": {
            "input": 0.0005,
            "output": 0.0015,
        },
    }

    @classmethod
    def calculate_cost(
        cls,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Calculate estimated cost for API call.

        Args:
            model: OpenAI model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        if model not in cls.PRICING:
            raise ValueError(f"Unknown model: {model}")

        input_cost = (prompt_tokens / 1000) * cls.PRICING[model]["input"]
        output_cost = (completion_tokens / 1000) * cls.PRICING[model]["output"]

        return round(input_cost + output_cost, 6)
```

#### 기능 3: 봇 서비스 계측 (Instrumentation)

```python
# src/services/student_bot.py (수정)
async def generate_response(self, teacher_content: str, history: list[dict]) -> str:
    response = await self.client.chat.completions.create(
        model=self.model,
        temperature=self.temperature,
        max_tokens=self.max_tokens,
        messages=[...],
    )

    # Phase 3: Log API usage
    usage = response.usage
    cost = CostCalculator.calculate_cost(
        model=self.model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
    )

    # Store usage log in database
    await self._log_api_usage(
        bot_type="student",
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost=cost,
    )

    return response.choices[0].message.content
```

#### 기능 4: 비용 메트릭 API 구현

```python
# src/api/routes/admin_chatbot_config.py (수정)
@router.get("/costs", response_model=CostMetricsResponse)
async def get_cost_metrics(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    days: int = 7,
):
    """Get API usage and cost metrics."""
    _check_admin_role(user)

    # Calculate date range
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Query usage logs
    result = await db.execute(
        select(APIUsageLog)
        .where(APIUsageLog.created_at >= start_date)
    )
    logs = result.scalars().all()

    # Aggregate metrics
    total_calls = len(logs)
    total_tokens = sum(log.total_tokens for log in logs)
    total_cost = sum(log.estimated_cost for log in logs)

    # Group by model
    usage_by_model = {}
    for log in logs:
        if log.model not in usage_by_model:
            usage_by_model[log.model] = {
                "calls": 0,
                "tokens": 0,
                "cost": 0.0,
            }
        usage_by_model[log.model]["calls"] += 1
        usage_by_model[log.model]["tokens"] += log.total_tokens
        usage_by_model[log.model]["cost"] += log.estimated_cost

    # Group by bot type
    usage_by_bot = {}
    for log in logs:
        if log.bot_type not in usage_by_bot:
            usage_by_bot[log.bot_type] = {
                "calls": 0,
                "cost": 0.0,
            }
        usage_by_bot[log.bot_type]["calls"] += 1
        usage_by_bot[log.bot_type]["cost"] += log.estimated_cost

    return CostMetricsResponse(
        date_range={
            "start": start_date.isoformat(),
            "end": datetime.now(timezone.utc).isoformat(),
        },
        total_api_calls=total_calls,
        total_tokens=total_tokens,
        estimated_cost=round(total_cost, 2),
        usage_by_model=usage_by_model,
        usage_by_bot_type=usage_by_bot,
    )
```

---

## 8. 성능 최적화

### 8.1 캐싱 전략

**현재 구현**:
- **TTL (Time-To-Live)**: 5분 (300초)
- **Invalidation**: 수동 (설정 업데이트 시)
- **Thread Safety**: `asyncio.Lock` 사용

**최적화 옵션**:

```python
# Option 1: 더 긴 TTL (개발 환경)
cache = BotConfigCache(ttl_seconds=600)  # 10 minutes

# Option 2: Redis 캐시 (프로덕션)
class RedisBotConfigCache(BotConfigCache):
    def __init__(self, redis_url: str, ttl_seconds: int = 300):
        self.redis = aioredis.from_url(redis_url)
        self._ttl = ttl_seconds

    async def get_global_config(self, db: AsyncSession) -> dict:
        # Try Redis first
        cached = await self.redis.get("global_config")
        if cached:
            return json.loads(cached)

        # Cache miss - load from DB
        configs = await self._load_from_db(db)

        # Store in Redis
        await self.redis.setex(
            "global_config",
            self._ttl,
            json.dumps(configs),
        )

        return configs
```

### 8.2 데이터베이스 쿼리 최적화

**인덱스 활용**:

```sql
-- 이미 생성된 인덱스
CREATE INDEX idx_chatbot_config_key ON chatbot_config(config_key);
CREATE INDEX idx_chatbot_audit_key ON chatbot_config_audit(config_key);
CREATE INDEX idx_chatbot_audit_timestamp ON chatbot_config_audit(changed_at);

-- 추가 권장 인덱스 (Phase 3)
CREATE INDEX idx_api_usage_session_timestamp ON api_usage_log(session_id, created_at);
CREATE INDEX idx_api_usage_model_timestamp ON api_usage_log(model, created_at);
```

**쿼리 최적화 예시**:

```python
# ❌ N+1 쿼리 문제
for scenario in scenarios:
    bot_config = await load_bot_config(scenario.id)  # N번 DB 쿼리

# ✅ 배치 로딩
scenario_ids = [s.id for s in scenarios]
bot_configs = await load_bot_configs_batch(scenario_ids)  # 1번 DB 쿼리
```

### 8.3 Rate Limiting 튜닝

**현재 설정**:
- `GET /admin/chatbot-config`: 30/min (기본값)
- `PUT /admin/chatbot-config`: 10/min
- `POST /admin/chatbot-config/reset`: 5/min

**프로덕션 권장 설정**:

```python
# src/api/routes/admin_chatbot_config.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/hour"],  # 전역 제한
    enabled=not config.TESTING,
)

@router.get("/")
@limiter.limit("60/minute")  # 읽기 작업: 관대하게

@router.put("/")
@limiter.limit("20/minute", per_method=True)  # 쓰기 작업: 엄격하게

@router.post("/reset")
@limiter.limit("3/hour")  # 위험한 작업: 매우 엄격하게
```

### 8.4 성능 메트릭 모니터링

**Prometheus 메트릭 추가** (선택 사항):

```python
# src/api/routes/admin_chatbot_config.py
from prometheus_client import Counter, Histogram

config_update_counter = Counter(
    'chatbot_config_updates_total',
    'Total number of configuration updates'
)

config_load_duration = Histogram(
    'chatbot_config_load_duration_seconds',
    'Time taken to load bot configuration'
)

@router.put("/")
async def update_chatbot_config(...):
    config_update_counter.inc()  # Increment counter
    # ... (update logic) ...
    return {"message": "Updated"}

async def _load_bot_config(self, scenario: Scenario) -> dict:
    with config_load_duration.time():  # Measure duration
        db_config = await bot_config_cache.get_global_config(self.db)
        # ... (loading logic) ...
```

---

## 참고 자료

### 관련 문서
- **관리자 가이드**: `/docs/admin_chatbot_config_guide.md` - 비기술 사용자를 위한 UI 가이드
- **보안 가이드**: `/docs/security.md` - 보안 권장사항 및 설정
- **배포 가이드**: `/docs/deployment.md` - 프로덕션 배포 절차
- **README**: `/README.md` - 프로젝트 개요 및 빠른 시작

### API 문서
- **Swagger UI**: `http://localhost:8000/docs` - 인터랙티브 API 문서
- **ReDoc**: `http://localhost:8000/redoc` - 대안 API 문서 뷰어

### 외부 리소스
- **OpenAI API 문서**: https://platform.openai.com/docs
- **FastAPI 공식 문서**: https://fastapi.tiangolo.com
- **SQLAlchemy 2.0 문서**: https://docs.sqlalchemy.org/en/20/
- **Pydantic 문서**: https://docs.pydantic.dev

---

## 변경 이력

| 버전 | 날짜 | 변경 사항 |
|------|------|----------|
| 1.0 | 2025-11-07 | 초판 작성 (Phase 2 완료 기준) |

---

**문서 작성자**: Misconception Platform Team
**문의**: dev@misconception-platform.com
**GitHub**: https://github.com/misconcept_platform
