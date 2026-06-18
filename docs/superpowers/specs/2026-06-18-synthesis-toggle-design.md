# 분석 보고서 서술형(synthesis) 분석 on/off 전역 스위치

- **작성일:** 2026-06-18
- **브랜치(예정):** `feat/synthesis-toggle`
- **저장소:** DomineYH/misconcept_platform
- **상태:** 설계 승인 대기 → 이슈 등록

## 1. 배경 / 문제

세션 분석 보고서 **상단**에는 "대화에 대한 분석 내용"(서술형 피드백)이 표시된다.
이 서술형 내용은 분석 파이프라인의 **synthesis 단계**가 생성하며, 가장 비싼 LLM
호출이다.

| 단계 | 산출물 | 비용 | 보고서 위치 |
|------|--------|------|-------------|
| 1. Greeting 필터 | 인사말 제거 | 저렴 | — |
| 2. **분류(classification)** | 질문별 레이블 + **수준(우수/개선)** | reasoning=low, 2.5K tok/질문 | 상세 탭 (대화코칭/우수한 점/개선할 점) |
| 3. **종합(synthesis)** | 서술형 분석 (`brief_feedback`, `strengths`, `improvements`, `dialogue_coaching`) | **gpt-5.2, reasoning=high, 최대 8K→12K tok** | **보고서 상단 박스** |

토큰 사용량과 분석 시간을 절약하기 위해, 관리자가 **synthesis 단계를 전역으로
끌 수 있는 on/off 스위치**가 필요하다.

- **ON (기본값, 현재 동작):** synthesis 생성 → 상단 서술형 박스 + 수준 분류 모두 표시
- **OFF:** synthesis 건너뜀 → 상단 서술형 박스 **완전히 숨김**, 수준 분류(상세 탭)만 표시

## 2. 핵심 통찰 (왜 이 설계가 깔끔한가)

`src/api/routes/session_analysis.py` 의 `get_analysis()` 와 템플릿을 분석한 결과:

- 보고서 상단 서술형 박스(`src/templates/analysis.html:17-27`)는 **오직
  `feedback_sections` (= synthesis payload)** 에서만 나온다.
- 상세 탭(대화코칭/우수한 점/개선할 점)은 `messages` / `questions` 의 **`grade`/`level`
  (classification 결과)** 으로 렌더되며 synthesis와 **무관**하다. 조건도
  `feedback_status != 'failed'` 라서 synthesis가 없어도 표시된다.

따라서 **synthesis 단계만 게이팅**하면 사용자가 원하는 동작("OFF = 수준 분류만")이
정확히 달성되고, 가장 비싼 LLM 호출이 절약된다. classification 로직은 손대지 않는다.

## 3. 설계 결정 (확정)

| 항목 | 결정 |
|------|------|
| 스위치 범위 | **관리자 전역 설정** (세션별/프레임워크별 아님) |
| 저장 방식 | **DB 기반, 런타임 토글** (재배포 불필요) |
| 저장소 | 신규 최소 KV 테이블 `app_setting` |
| 기본값 | **ON** (현재 동작 보존) |
| OFF일 때 상단 박스 | **완전히 숨김** (안내 문구 없음) |
| OFF일 때 상세 탭 | 그대로 표시 (수준 분류 기반) |

## 4. 컴포넌트 설계

### 4.1 저장소 — 신규 `app_setting` KV 테이블

현재 전역 설정용 KV 저장소가 없다. 최소 키-값 테이블을 추가한다.

- **마이그레이션:** `src/db/migrations/023_add_app_setting.sql` (+ down 파일)
  - `init_schema.py` 의 `SCHEMA_SQL` 에도 `CREATE TABLE IF NOT EXISTS app_setting` 추가
    (신규 DB 초기화 경로 커버)
- **모델:** `src/models/app_setting.py` → `AppSetting`
  - 컬럼: `key TEXT PRIMARY KEY`, `value TEXT NOT NULL`, `updated_at DATETIME`
- **키 상수:** `analysis_synthesis_enabled`, 값 `"true"` / `"false"`

> **대안 검토:** (a) ENV 전용 플래그 — 런타임 토글 불가로 탈락. (b) 전용 boolean
> 단일행 테이블 — 단일 용도면 가능하나, KV가 향후 전역 토글 확장에 더 자연스럽고
> 기존 admin DB 설정 패턴과 일관됨. 모델·로직은 최소로 유지(YAGNI).

### 4.2 설정 서비스 — `src/services/app_settings.py`

작은 헬퍼 모듈로 경계를 명확히 한다.

- `async def is_synthesis_enabled(db) -> bool` — row 없으면 기본 `True` 반환
- `async def set_synthesis_enabled(db, enabled: bool) -> None` — upsert

> 책임: 설정 키의 읽기/쓰기와 기본값 정책 한 곳 집중. 파이프라인·라우트는 이 함수만
> 호출하고 KV 저장 형식은 모른다.

### 4.3 파이프라인 게이팅 — `src/services/analysis_pipeline.py`

- `analyze_session(...)` 와 `run_llm_pipeline(...)` 에 `synthesis_enabled: bool = True`
  인자 추가.
- `run_llm_pipeline` **Step 3**: `synthesis_enabled` 가 False면 synthesis LLM 호출을
  **건너뛰고**:
  - `payload = {"version": 1, "brief_feedback": [], "strengths": [], "improvements": [], "dialogue_coaching": []}`
  - `synthesis_status = "skipped"`
  - `synth_model = "skipped"`, `synth_hash = "skipped"`, synthesis API usage 로그 없음
- `analyze_session`: `feedback` 도출 시 `status == "skipped"` 면 `feedback = None`
  (FALLBACK 문구를 쓰지 않음 — 실패가 아니라 의도적 생략).
  `SessionFeedbackReport` 는 `status="skipped"` 로 기록(또는 미기록; 기록 권장 →
  보고서 렌더가 상태로 분기 가능).

### 4.4 호출 지점에서 설정 주입 (2곳)

- `src/api/routes/session_analysis.py:111` (`analyze_session_endpoint`)
- `src/api/routes/admin_session_actions.py:258` (관리자 세션 종료 시 자동 분석)

두 곳 모두 `analyze_session` 호출 직전 `is_synthesis_enabled(db)` 를 읽어 인자로 전달.

### 4.5 보고서 렌더 — `src/templates/analysis.html`

- `feedback_status == "skipped"` 분기 추가:
  - 상단 서술형 박스 블록(현재 `feedback_status in ('ok','degraded')` 분기)을 렌더하지
    **않음** → 박스 완전 숨김.
  - `else`/legacy 분기로 빠지지 않도록 명시적 분기 처리.
- 상세 탭 include 조건 `feedback_status != 'failed'` 는 그대로 → `skipped` 도 통과하여
  수준 분류 탭 표시.
- 동일 분기를 modal 파셜(`partials/analysis_modal.html`)에도 반영 (상단 박스가
  거기에도 있으면).
- `get_analysis()` 응답에 `feedback_status` 가 이미 포함됨 → DB 의 report.status 가
  `"skipped"` 로 전달되도록 4.3 에서 기록.

### 4.6 관리자 UI — `src/api/routes/admin_settings.py` (신규)

- `GET /admin/settings` — 현재 토글 상태로 설정 페이지 렌더
  (`src/templates/admin/settings.html` 신규)
- `POST /admin/settings/synthesis` — 토글 업데이트 후 리다이렉트/파셜 반환
  - `get_admin_user` 의존성으로 admin 전용
  - CSRF: 전역 `CSRFMiddleware`(Double Submit Cookie, `x-csrf-token`)가 자동 적용
- `src/templates/admin/dashboard.html` 에 "분석 설정" action-card 추가
- 라우터를 `src/main.py` (또는 라우터 등록 지점)에 include

## 5. 데이터 흐름

```
[관리자] /admin/settings 토글
   └→ POST /admin/settings/synthesis → set_synthesis_enabled(db, False)
        └→ app_setting[analysis_synthesis_enabled] = "false"

[세션 종료/분석 트리거]
   analyze_session_endpoint  /  admin auto-analyze
     └→ enabled = is_synthesis_enabled(db)   # False
         └→ analyze_session(..., synthesis_enabled=False)
             └→ run_llm_pipeline(..., synthesis_enabled=False)
                 ├ Step1 greeting (그대로)
                 ├ Step2 classification → 수준(우수/개선) (그대로)
                 └ Step3 synthesis → SKIP, status="skipped", 빈 payload
         └→ SessionFeedbackReport.status = "skipped"

[보고서 조회] /sessions/{id}/analysis_page
   └→ feedback_status="skipped"
       ├ 상단 서술형 박스 → 렌더 안 함 (숨김)
       └ 상세 탭(수준 분류) → 표시
```

## 6. 에러 / 엣지 케이스

- **설정 row 없음(최초):** `is_synthesis_enabled` 기본 `True` → 현재 동작 보존.
- **기존(legacy) 보고서:** `feedback_status="legacy"` 분기 그대로 유지 — 영향 없음.
- **OFF로 분석 후 ON 전환:** 이미 생성된 `skipped` 보고서는 그대로. 재분석은 기존
  요약 존재 시 단락(short-circuit)되므로(현재 `existing_summary` 체크), 재생성하려면
  기존 흐름을 따른다. (재분석 UX 변경은 **이번 범위 밖**.)
- **synthesis 실제 실패 vs skipped 구분:** `failed` 와 `skipped` 는 별도 status.
  `failed` 는 상단에 실패 메시지, `skipped` 는 상단 숨김.

## 7. 테스트 전략

- **설정 서비스** (`tests/unit/test_app_settings.py`):
  - row 없을 때 기본값 True
  - set→get 라운드트립, true/false 전환
- **파이프라인** (`tests/unit/test_analysis_pipeline_synthesis_toggle.py`):
  - `synthesis_enabled=False` → synthesizer 호출 안 됨(mock 검증), status="skipped",
    빈 payload, synthesis API usage 로그 없음
  - `synthesis_enabled=True` → 기존 동작 유지 (회귀)
- **라우트** (`tests/.../test_admin_settings.py`):
  - admin GET/POST 토글 동작
  - 비-admin 접근 차단(403/redirect)
- **템플릿** (`tests/templates/test_analysis_skipped_state.py`):
  - `feedback_status="skipped"` 시 상단 서술형 박스 미표시
  - 상세 탭(수준 분류)은 표시됨
- 기존 분석 테스트 회귀 확인(전체 스위트는 pre-commit에서 자동 실행).

## 8. Success Criteria (완료 인수 기준)

1. `app_setting` 테이블 + `AppSetting` 모델 추가, 마이그레이션 적용 가능.
2. 관리자 `/admin/settings` 에서 "대화 서술형 분석" on/off 토글, DB에 즉시 반영(런타임).
3. 토글 **OFF** 상태로 세션 분석 시: synthesis LLM 호출이 발생하지 않음(토큰/시간 절약),
   `SessionFeedbackReport.status="skipped"`.
4. OFF로 분석된 세션 보고서: **상단 서술형 박스 완전 숨김**, 수준 분류 상세 탭 정상 표시.
5. 토글 **ON**(기본값): 기존 동작과 동일(회귀 없음).
6. 신규/회귀 테스트 통과.

## 9. 범위 밖 (Out of scope)

- 세션별·프레임워크별 토글
- 기존 `skipped` 보고서의 재분석/재생성 UX
- classification(수준 분류) 단계 자체의 비용 최적화
- synthesis 프롬프트/모델 변경
