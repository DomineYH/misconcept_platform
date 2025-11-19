# 챗봇 설정 기능 삭제 계획

## 배경 및 목적

**현재 상태**: 챗봇 설정을 데이터베이스(`chatbot_config` 테이블)와 관리자 UI를 통해 관리
**변경 이유**: 설정이 자주 변경되지 않으며, .env 파일로 통합 관리하는 것이 더 단순하고 효율적
**목표**: 데이터베이스 기반 챗봇 설정 기능을 제거하고 .env로 일원화

---

## 현재 챗봇 설정 구조 분석

### 1. 설정 우선순위 (현재)
```python
# SessionManager._load_bot_config() 기준
1. 시나리오별 오버라이드 (scenario.chat_model, chat_temperature 등)
2. 글로벌 DB 설정 (chatbot_config 테이블)
3. 환경 변수 (.env의 CHAT_MODEL, ANALYSIS_MODEL)
4. 하드코딩된 기본값
```

### 2. 관리되는 설정값

#### StudentBot 설정
- `student_bot.model` → .env: `CHAT_MODEL`
- `student_bot.temperature` → 기본값 0.7 (DB에서 관리 중)
- `student_bot.max_tokens` → 기본값 150 (DB에서 관리 중)

#### TutorBot 설정
- `tutor_bot.model` → .env: `ANALYSIS_MODEL`
- `tutor_bot.temperature` → 기본값 0.3 (DB에서 관리 중)
- `tutor_bot.max_tokens` → 기본값 100 (DB에서 관리 중)
- `tutor_bot.intervention_threshold` → 기본값 3 (DB에서 관리 중)

### 3. 데이터 흐름
```
관리자 UI → API 엔드포인트 → chatbot_config 테이블 → 캐시 → SessionManager → Bot 초기화
```

---

## 삭제 대상 파일 및 코드

### 📁 완전 삭제 파일

#### 1. 라우트
- **파일**: `src/api/routes/admin_chatbot_config.py` (452줄)
- **내용**: 챗봇 설정 관리 API 엔드포인트 전체
  - `GET /admin/chatbot-config/settings` - 설정 페이지
  - `GET /admin/chatbot-config/` - 설정 조회
  - `PUT /admin/chatbot-config/` - 설정 업데이트
  - `GET /admin/chatbot-config/costs` - 비용 메트릭 (Phase 3 placeholder)
  - `POST /admin/chatbot-config/reset` - 기본값 재설정
- **의존성**:
  - `ChatbotConfig`, `ChatbotConfigAudit` 모델
  - `bot_config_cache` 서비스
  - Pydantic 스키마: `BotConfigUpdate`, `BotConfigResponse`, `CostMetricsResponse`

#### 2. 모델
- **파일**: `src/models/chatbot_config.py` (87줄)
- **내용**:
  - `ChatbotConfig` 클래스: 글로벌 챗봇 설정 모델
  - `ChatbotConfigAudit` 클래스: 설정 변경 감사 로그
- **의존성**:
  - `User` 모델과 관계 (`updater`, `user`)
  - `Base` 클래스 상속

#### 3. 서비스
- **파일**: `src/services/config_cache.py` (120줄)
- **내용**:
  - `BotConfigCache` 클래스: 챗봇 설정 캐싱 시스템
  - `bot_config_cache` 싱글톤 인스턴스
- **기능**:
  - 5분 TTL 캐시
  - 글로벌 설정 조회 (`get_global_config`)
  - 시나리오별 설정 조회 (`get_scenario_config` - Phase 2 미구현)
  - 캐시 무효화 (`invalidate`, `invalidate_scenario`)

#### 4. 템플릿
- **파일**: `src/templates/admin/chatbot_settings.html` (502줄)
- **내용**: 챗봇 설정 관리 UI 페이지 전체
- **기능**:
  - StudentBot/TutorBot 설정 폼
  - Temperature/Max Tokens 슬라이더
  - 모델 표시 (읽기 전용, .env 안내)
  - 설정 저장/리셋 버튼
  - 실시간 validation 및 캐시 검증

#### 5. 테스트
- **파일**: `tests/integration/test_admin_chatbot_config.py`
- **내용**: 챗봇 설정 API 통합 테스트
- **테스트 케이스**:
  - 설정 조회 테스트
  - 설정 업데이트 테스트
  - 권한 검증 테스트
  - 캐시 무효화 검증
  - Rate limiting 테스트

#### 6. 문서
- **파일 1**: `docs/admin_chatbot_config_guide.md`
  - 관리자용 챗봇 설정 가이드
- **파일 2**: `docs/developer_chatbot_config_guide.md`
  - 개발자용 설정 시스템 문서
- **파일 3**: `docs/tutor_threshold_slider_verification.md`
  - 튜터봇 임계값 슬라이더 검증 문서

#### 7. 마이그레이션
- **파일 1**: `src/db/migrations/001_add_chatbot_config.sql`
  - `chatbot_config` 테이블 생성
  - `chatbot_config_audit` 테이블 생성
  - 기본값 seed 데이터
- **파일 2**: `src/db/migrations/002_scenario_bot_config.sql`
  - `scenario` 테이블에 챗봇 설정 컬럼 추가
  - `chat_model`, `chat_temperature`, `tutor_enabled`, `tutor_intervention_threshold`

---

### ✂️ 부분 수정 파일

#### 1. `src/models/user.py`
**수정 위치**: 45-47줄
```python
# 삭제할 관계
config_updates: Mapped[list["ChatbotConfig"]] = relationship(
    "ChatbotConfig", back_populates="updater"
)
```
**변경 후**: 해당 relationship 제거

---

#### 2. `src/models/__init__.py`
**수정 위치**: import 구문
```python
# 삭제할 import
from src.models.chatbot_config import ChatbotConfig, ChatbotConfigAudit
```
**변경 후**: 해당 import 제거

---

#### 3. `src/services/session_mgr.py`
**핵심 변경**: `_load_bot_config()` 메서드 로직 단순화

**현재 코드** (195-245줄):
```python
async def _load_bot_config(self, scenario: Scenario) -> dict:
    """Load bot config: Scenario > Global > Env > Default."""
    # Load global config from database using cache (<10ms)
    db_config = await bot_config_cache.get_global_config(self.db)

    # Apply scenario-specific overrides with proper priority
    return {
        "student_model": (
            scenario.chat_model
            or db_config.get("student_bot.model")
            or config.CHAT_MODEL
        ),
        "student_temperature": (
            scenario.chat_temperature
            if scenario.chat_temperature is not None
            else float(db_config.get("student_bot.temperature", "0.7"))
        ),
        # ... 나머지 설정
    }
```

**변경 후**:
```python
def _load_bot_config(self, scenario: Scenario) -> dict:
    """Load bot config from .env and scenario overrides.

    Configuration priority:
    1. Scenario-specific overrides (if set)
    2. Environment variables (.env)
    3. Hardcoded defaults

    Note: Database-based global config removed.
          All defaults now managed via .env.
    """
    return {
        # StudentBot configuration
        "student_model": (
            scenario.chat_model  # Scenario override
            or config.CHAT_MODEL  # .env fallback
            or "gpt-4-turbo"  # Default
        ),
        "student_temperature": (
            scenario.chat_temperature
            if scenario.chat_temperature is not None
            else config.STUDENT_TEMPERATURE  # NEW: .env 변수
            if hasattr(config, 'STUDENT_TEMPERATURE')
            else 0.7  # Default
        ),
        "student_max_tokens": (
            config.STUDENT_MAX_TOKENS  # NEW: .env 변수
            if hasattr(config, 'STUDENT_MAX_TOKENS')
            else 150  # Default
        ),

        # TutorBot configuration
        "tutor_enabled": scenario.tutor_enabled,
        "tutor_model": (
            config.ANALYSIS_MODEL  # .env fallback
            or "gpt-3.5-turbo"  # Default
        ),
        "tutor_temperature": (
            config.TUTOR_TEMPERATURE  # NEW: .env 변수
            if hasattr(config, 'TUTOR_TEMPERATURE')
            else 0.3  # Default
        ),
        "tutor_max_tokens": (
            config.TUTOR_MAX_TOKENS  # NEW: .env 변수
            if hasattr(config, 'TUTOR_MAX_TOKENS')
            else 100  # Default
        ),
        "tutor_intervention_threshold": (
            scenario.tutor_intervention_threshold
            if scenario.tutor_intervention_threshold is not None
            else config.TUTOR_INTERVENTION_THRESHOLD  # NEW: .env 변수
            if hasattr(config, 'TUTOR_INTERVENTION_THRESHOLD')
            else 3  # Default
        ),
    }
```

**삭제할 import** (13줄):
```python
from src.services.config_cache import bot_config_cache
```

**변경 사항**:
- ❌ `async` 함수 → ✅ 일반 함수 (DB 조회 제거)
- ❌ `bot_config_cache.get_global_config()` 호출 제거
- ✅ .env 환경 변수 직접 사용
- ✅ 하드코딩된 기본값 fallback

---

#### 4. `src/templates/admin/dashboard.html`
**수정 위치**: 106줄
```html
<!-- 삭제할 링크 -->
<a href="/admin/chatbot-config/settings" class="btn btn-secondary">
  🤖 챗봇 설정
</a>
```
**변경 후**: 해당 버튼 제거

---

#### 5. `src/config.py`
**추가할 환경 변수**:
```python
# ===== Chatbot Configuration (기존) =====
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4-turbo")
ANALYSIS_MODEL: str = os.getenv("ANALYSIS_MODEL", "gpt-3.5-turbo")

# ===== NEW: Chatbot Parameter Configuration =====
# StudentBot settings
STUDENT_TEMPERATURE: float = float(
    os.getenv("STUDENT_TEMPERATURE", "0.7")
)
STUDENT_MAX_TOKENS: int = int(
    os.getenv("STUDENT_MAX_TOKENS", "150")
)

# TutorBot settings
TUTOR_TEMPERATURE: float = float(
    os.getenv("TUTOR_TEMPERATURE", "0.3")
)
TUTOR_MAX_TOKENS: int = int(
    os.getenv("TUTOR_MAX_TOKENS", "100")
)
TUTOR_INTERVENTION_THRESHOLD: int = int(
    os.getenv("TUTOR_INTERVENTION_THRESHOLD", "3")
)
```

---

#### 6. `.env` (또는 `.env.example`)
**추가할 설정**:
```bash
# ===== Chatbot Models =====
CHAT_MODEL=gpt-4-turbo
ANALYSIS_MODEL=gpt-3.5-turbo

# ===== StudentBot Parameters =====
STUDENT_TEMPERATURE=0.7        # 0.0-2.0 (높을수록 창의적)
STUDENT_MAX_TOKENS=150         # 최대 응답 길이

# ===== TutorBot Parameters =====
TUTOR_TEMPERATURE=0.3          # 0.0-2.0 (일관적인 피드백)
TUTOR_MAX_TOKENS=100           # 최대 피드백 길이
TUTOR_INTERVENTION_THRESHOLD=3 # 질문 10개당 개입 횟수 (1-10)
```

---

#### 7. `README.md`
**수정 위치**: 챗봇 설정 관련 안내 부분
- 관리자 UI를 통한 설정 변경 안내 → .env 파일 수정 안내로 변경
- 데이터베이스 설정 우선순위 설명 제거
- 환경 변수 기반 설정 방법 추가

---

## 데이터베이스 마이그레이션 전략

### 옵션 1: 테이블 완전 삭제 (권장)
**생성**: `src/db/migrations/003_remove_chatbot_config.sql`

```sql
-- Migration: Remove chatbot configuration tables
-- Reason: Settings moved to .env for simplification
-- Date: 2025-11-07

-- ============================================
-- Drop tables (audit first for FK constraint)
-- ============================================
DROP TABLE IF EXISTS chatbot_config_audit;
DROP TABLE IF EXISTS chatbot_config;

-- ============================================
-- Remove scenario bot config columns
-- ============================================
-- SQLite doesn't support DROP COLUMN directly
-- Need to recreate table without these columns

-- 1. Create new scenario table without bot config columns
CREATE TABLE scenario_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    prompt TEXT NOT NULL,
    student_profile TEXT,
    framework_id INTEGER REFERENCES framework(id),
    created_by INTEGER NOT NULL REFERENCES user(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- 2. Copy data from old table
INSERT INTO scenario_new (
    id, title, prompt, student_profile,
    framework_id, created_by, created_at, is_active
)
SELECT
    id, title, prompt, student_profile,
    framework_id, created_by, created_at, is_active
FROM scenario;

-- 3. Drop old table and rename new table
DROP TABLE scenario;
ALTER TABLE scenario_new RENAME TO scenario;

-- 4. Recreate indexes
CREATE INDEX IF NOT EXISTS idx_scenario_framework
    ON scenario(framework_id);
CREATE INDEX IF NOT EXISTS idx_scenario_active
    ON scenario(is_active);
```

**영향**:
- ✅ 데이터베이스 정규화 (불필요한 컬럼 제거)
- ⚠️ 기존 시나리오별 챗봇 설정 데이터 손실
- ⚠️ `chatbot_config_audit` 감사 로그 손실

---

### 옵션 2: 테이블 유지 (데이터 보존)
**장점**: 기존 설정 데이터 및 감사 로그 보존
**단점**: 사용하지 않는 테이블 유지, 스키마 복잡도 증가

**권장**: 프로덕션 환경이 아니므로 **옵션 1 (완전 삭제)** 권장

---

## 라우트 등록 제거

### `src/main.py` 또는 라우터 등록 파일
**수정 위치**: admin_chatbot_config 라우터 등록 부분
```python
# 삭제할 라우터 등록
from src.api.routes import admin_chatbot_config

app.include_router(admin_chatbot_config.router)
```

---

## 시나리오별 설정 처리

### 현재 상황
`scenario` 테이블의 다음 컬럼들이 시나리오별 챗봇 설정 오버라이드 제공:
- `chat_model` (VARCHAR(50))
- `chat_temperature` (REAL)
- `tutor_enabled` (BOOLEAN)
- `tutor_intervention_threshold` (INTEGER)

### 옵션 분석

#### 옵션 A: 컬럼 유지 (권장)
**이유**:
- 시나리오별 챗봇 동작 커스터마이징은 유효한 요구사항
- 예: 초등학생용 시나리오는 temperature 높게, 중학생용은 낮게
- 글로벌 설정(.env)과 시나리오별 오버라이드는 별개 문제

**변경**: 없음 (컬럼 유지)

**SessionManager 로직**:
```python
"student_temperature": (
    scenario.chat_temperature  # 시나리오 오버라이드 우선
    if scenario.chat_temperature is not None
    else config.STUDENT_TEMPERATURE  # .env 기본값
)
```

---

#### 옵션 B: 컬럼 삭제
**장점**: 데이터베이스 단순화
**단점**: 시나리오별 커스터마이징 불가능

**시나리오별 커스터마이징이 필요 없다면** 이 옵션 선택

---

## 변경 영향 분석

### 1. 기능적 영향
| 항목 | 변경 전 | 변경 후 | 영향도 |
|------|---------|---------|--------|
| 설정 변경 방법 | 관리자 UI | .env 파일 수정 → 서버 재시작 | **중** |
| 설정 변경 이력 | DB audit 로그 | 없음 (Git으로 대체) | **저** |
| 실시간 설정 반영 | 즉시 (캐시 무효화) | 서버 재시작 필요 | **중** |
| 설정 백업/복구 | DB dump | .env 파일 버전 관리 | **저** |
| 시나리오별 설정 | DB 오버라이드 | 유지 (옵션 A) / 불가능 (옵션 B) | **중/고** |

### 2. 코드 복잡도
- **감소**: 라우트 452줄, 모델 87줄, 캐시 120줄 등 **약 1,500줄 제거**
- **단순화**: SessionManager의 설정 로드 로직이 DB 조회 → 환경 변수 참조로 변경
- **유지보수**: 설정 관리 포인트가 단일화 (.env만 관리)

### 3. 성능
- **긍정적**: DB 조회 제거로 설정 로드 속도 향상 (~10ms → ~0.1ms)
- **긍정적**: 캐시 시스템 불필요로 메모리 사용량 감소
- **중립**: 서버 재시작이 필요하지만, 설정 변경 빈도가 낮으므로 실질적 영향 미미

### 4. 보안
- **긍정적**: 설정 변경 권한 관리 불필요 (파일 시스템 권한으로 충분)
- **중립**: .env 파일 보안은 기존 방식과 동일하게 유지

---

## 삭제 작업 순서

### Phase 1: 준비 단계
1. ✅ **코드 분석 완료** (현재 단계)
2. ⬜ Git 브랜치 생성: `feature/remove-chatbot-config-ui`
3. ⬜ 현재 DB의 `chatbot_config` 데이터 백업
   ```bash
   sqlite3 dialogue_sim.db ".dump chatbot_config" > backup_chatbot_config.sql
   sqlite3 dialogue_sim.db ".dump chatbot_config_audit" > backup_config_audit.sql
   ```

### Phase 2: .env 설정 추가
4. ⬜ `src/config.py`에 새 환경 변수 추가
5. ⬜ `.env` 및 `.env.example`에 설정값 추가
6. ⬜ 기존 DB 설정값을 .env로 이전 (수동 확인)

### Phase 3: 코드 수정
7. ⬜ `src/services/session_mgr.py` 수정
   - `_load_bot_config()` 단순화
   - `bot_config_cache` import 제거
8. ⬜ `src/models/user.py` 수정
   - `config_updates` relationship 제거

### Phase 4: 파일 삭제
9. ⬜ 완전 삭제 파일 제거 (7개 파일)
   ```bash
   rm src/api/routes/admin_chatbot_config.py
   rm src/models/chatbot_config.py
   rm src/services/config_cache.py
   rm src/templates/admin/chatbot_settings.html
   rm tests/integration/test_admin_chatbot_config.py
   rm docs/admin_chatbot_config_guide.md
   rm docs/developer_chatbot_config_guide.md
   rm docs/tutor_threshold_slider_verification.md
   ```
10. ⬜ `src/models/__init__.py`에서 import 제거
11. ⬜ `src/main.py`에서 라우터 등록 제거
12. ⬜ `src/templates/admin/dashboard.html`에서 챗봇 설정 링크 제거

### Phase 5: 데이터베이스 마이그레이션
13. ⬜ `src/db/migrations/003_remove_chatbot_config.sql` 생성
14. ⬜ 마이그레이션 실행 또는 DB 재생성
    ```bash
    # 옵션 1: 마이그레이션 수동 실행
    sqlite3 dialogue_sim.db < src/db/migrations/003_remove_chatbot_config.sql

    # 옵션 2: DB 재생성 (개발 환경)
    rm dialogue_sim.db
    python -m src.db.seed
    ```

### Phase 6: 테스트 및 검증
15. ⬜ 서버 시작 확인
    ```bash
    uvicorn src.main:app --reload
    ```
16. ⬜ 기능 테스트
    - 시나리오 선택 → 채팅 시작 → 메시지 전송
    - StudentBot/TutorBot 응답 정상 동작 확인
    - 시나리오별 설정 오버라이드 동작 확인 (옵션 A 선택 시)
17. ⬜ 테스트 suite 실행
    ```bash
    pytest tests/
    ```
18. ⬜ 관리자 대시보드 접근 확인 (챗봇 설정 버튼 제거 확인)

### Phase 7: 문서 업데이트
19. ⬜ `README.md` 업데이트
    - 챗봇 설정 방법을 .env 기반으로 변경
    - 환경 변수 설명 추가
20. ⬜ `CHANGELOG.md` 또는 릴리스 노트 작성
21. ⬜ 배포 가이드 업데이트 (설정 마이그레이션 안내)

### Phase 8: 커밋 및 배포
22. ⬜ Git 커밋
    ```bash
    git add .
    git commit -m "refactor: remove chatbot config UI, migrate to .env

    - Remove database-based chatbot configuration
    - Remove admin UI for chatbot settings
    - Migrate all settings to .env for simplicity
    - Remove chatbot_config and chatbot_config_audit tables
    - Simplify SessionManager._load_bot_config()
    - Remove BotConfigCache service

    BREAKING CHANGE: Chatbot settings now managed via .env only
    "
    ```
23. ⬜ PR 생성 및 리뷰
24. ⬜ 배포 전 설정 파일 준비 (.env 업데이트)
25. ⬜ 배포

---

## 롤백 계획

만약 삭제 후 문제가 발생할 경우:

1. **코드 롤백**:
   ```bash
   git revert <commit-hash>
   ```

2. **데이터베이스 복원**:
   ```bash
   sqlite3 dialogue_sim.db < backup_chatbot_config.sql
   sqlite3 dialogue_sim.db < backup_config_audit.sql
   ```

3. **마이그레이션 롤백**:
   - `003_remove_chatbot_config.sql`의 역방향 마이그레이션 실행
   - 또는 DB를 이전 백업으로 복원

---

## 예상 질문 및 답변 (FAQ)

### Q1: 왜 관리자 UI를 제거하나요?
**A**: 챗봇 설정은 실시간으로 자주 변경되는 값이 아니며, .env로 관리하는 것이 더 단순하고 Git을 통한 버전 관리도 용이합니다. 코드 복잡도를 줄이고 유지보수를 쉽게 하기 위한 결정입니다.

### Q2: 시나리오별 설정은 어떻게 하나요?
**A**: 옵션 A를 선택하면 `scenario` 테이블의 설정 컬럼이 유지되므로, 시나리오 생성 시 또는 직접 DB 수정으로 설정 가능합니다. 향후 필요 시 시나리오 관리 UI를 추가할 수 있습니다.

### Q3: 설정 변경 이력은 어떻게 추적하나요?
**A**: .env 파일을 Git으로 관리하면 변경 이력 추적이 가능합니다. 다만, .env는 보안상 `.gitignore`에 포함되므로, 설정 템플릿(`.env.example`)만 버전 관리하는 것이 일반적입니다.

### Q4: 프로덕션 환경에서 설정을 바꾸려면?
**A**:
1. .env 파일 수정
2. 서버 재시작 (`systemctl restart misconcept_platform`)

Docker 환경이라면 환경 변수를 컨테이너 재시작 시 주입하면 됩니다.

### Q5: 캐시 성능 최적화가 사라지는데 괜찮나요?
**A**: 환경 변수 조회는 캐시 조회보다 훨씬 빠릅니다 (~0.1ms vs ~10ms). 오히려 성능이 개선됩니다.

---

## 체크리스트

- [ ] 모든 관련 파일 식별 완료
- [ ] 의존성 분석 완료
- [ ] 데이터 백업 계획 수립
- [ ] 마이그레이션 SQL 작성
- [ ] .env 설정 추가
- [ ] 코드 수정 완료
- [ ] 파일 삭제 완료
- [ ] 테스트 통과
- [ ] 문서 업데이트 완료
- [ ] 코드 리뷰 완료
- [ ] 배포 준비 완료

---

## 참고 자료

- **관련 Issue**: (해당되는 경우 링크)
- **설계 문서**: `docs/developer_chatbot_config_guide.md` (삭제 예정)
- **마이그레이션 히스토리**:
  - `001_add_chatbot_config.sql` (삭제 예정)
  - `002_scenario_bot_config.sql` (부분 롤백 예정)
  - `003_remove_chatbot_config.sql` (신규 작성 예정)

---

**작성일**: 2025-11-07
**작성자**: AI Assistant (사용자 요청에 따라 분석)
**검토 필요**: ✅ 실제 작업 전 개발자 최종 검토 필수
