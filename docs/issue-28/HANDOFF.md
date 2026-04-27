# Issue #28 — Handoff Document

**Branch:** `feat/issue-28-analysis-report-redesign`
**Status:** Implementation 완료, 회귀 fix 대기
**Date:** 2026-04-26
**Source plan:** `~/.gstack/projects/DomineYH-misconcept_platform/dominelinux-feat-issue-28-analysis-report-redesign-design-20260424-141916.md` (v2.2 APPROVED)

---

## 1. 결정된 것 (Decided)

### 스코프
- **Wedge-first phase 1**: 짧은 피드백 + stat 4칸 + [질문별 분석 보기] 토글. 탭 UI는 phase 2로 연기 (사용자 클릭률 ≥ 40% / 4주 후 결정)
- **새 테이블 `session_feedback_report`** (JSON-in-TEXT 거부). `SessionSummary.feedback`은 1줄 텍스트 유지하여 5개 consumer site (CSV export 3곳, admin API, 일반 API) 무영향
- **LLM 품질 게이트 사전 검증**: `evals/issue-28/` 인프라 완성, 전문가 라벨링은 외부 prerequisite로 분리

### 아키텍처
- LLM-first / DB-second atomic transaction (synthesis 실패 시 partial state 없음)
- `asyncio.gather` + `Semaphore(5)` 병렬 classify (p95 ~26s, 60s proxy timeout 이내)
- `derive_plain_feedback(payload) → str` 중앙 검증기로 5개 consumer 보호
- Regenerate endpoint: admin auth + rate-limit + `BEGIN EXCLUSIVE` 락 + synthesize-first-then-replace + 보존 분기 (synthesis failed, 또는 degraded → 기존 `ok` 보호)
- DB migration: raw SQL `019_*.sql`, `020_*.sql`, `021_*.sql` (Alembic 미사용 — 레포 컨벤션 준수)
- ApiUsageLog에 `operation` 컬럼 추가 (classification/synthesis/greeting 분리)
- PRAGMA `foreign_keys=ON` 모든 SQLite 연결에 적용

### UI/디자인
- 색상: `--color-info-bg` (#E3F2FD), `--color-info-text` (#0D47A1), `--color-mentor-border` (#1565C0) — 멘토 info 패밀리. **보라 금지** (DESIGN.md line 19)
- 클래스: flat `.analysis-wedge`, `.analysis-stat-grid`, `.analysis-stat-card`, `.analysis-brief-feedback`, `.analysis-detail-toggle` (BEM 미사용)
- 마크업: `<dl>`/`<dt>`/`<dd>` 시맨틱, `aria-label="대화 시간 5분 12초"` 풀 문장
- 4가지 상태 분기: `ok` / `degraded` / `failed` / `legacy`
- 누락 stat: `계산 불가` (0 표시 안 함)
- 버튼: `질문별 분석 보기 ▼` / `질문별 분석 접기 ▲` (`상세 분석` 안 씀, phase 2 탭 기대치 회피)
- 반응형: `<480` 1×4 stack, `480-767` 2×2 compact, `≥768` 2×2 roomy

### 테스트 패턴
- 통합 테스트는 컴포지트 fixture (`test_teacher`, `test_scenario`, `test_framework`, `sample_session_*`) 필수 — PRAGMA fk=ON 환경에서 manual row insert 금지
- `synthesis_mock` fixture (conftest.py:410) 사용으로 결정적 LLM 응답
- Async API 테스트는 인증 fixture 필수 (cookies 또는 `authenticated_async_client` 패턴)

---

## 2. 거부된 대안 (Rejected)

| 대안 | 거부 이유 |
|---|---|
| JSON-in-`SessionSummary.feedback` (v1 plan) | 5개 consumer site silently 깨짐 (CSV/admin) |
| 풀 모달 재작성 + 탭 한 번에 구현 | 60% 복잡도가 측정 안 된 사용 패턴에 투자됨 — wedge로 측정 후 결정 |
| 보라색 feedback 박스 | DESIGN.md line 19 명시 금지, 토큰 자체 부재 |
| Alembic 도입 | 레포 raw SQL migration 컨벤션과 충돌, 별도 인프라 작업 |
| 직렬 classify 유지 | p95 latency 74s → 60s proxy timeout 위반 |
| Synthesis at GET (lazy) | /analyze가 이미 무거운 엔드포인트, 재시도 시 side-effect 위험 |
| Regenerate DELETE-then-synthesize | LLM 실패 시 데이터 영구 손실 위험 |
| 상세 분석 버튼명 사용 | PDF 탭 레이아웃 기대치 설정, phase 1 wedge와 mismatch |
| BEM 클래스 네임스페이스 | 기존 `.analysis-*` flat 컨벤션과 불일치 |

---

## 3. 리스크 (Risks)

### 즉시 처리 필수
1. **회귀 8 fail + 14 errors** in 기존 테스트 3파일 — PRAGMA fk=ON이 잠재 결함 노출. 머지 전 fix 필요
2. **신규 코드 ruff 32 errors** (15 자동 fix) — worker-3-2가 final --fix 누락
3. **`tests/contract/snapshots/` 빈 디렉터리** — 첫 실행 시 byte-equal snapshot 생성 필요

### 모니터링 필요
4. **Retry storm 시 worst-case latency 96s** — 60s proxy timeout 초과 가능 (T6 가정 수용). production에서 실측 시 `ApiUsageLog.retry_count` ≥ 1% 발생 시 202+poll 패턴으로 후속 issue
5. **OpenAI prompt caching 미검증** — 1024 token prefix 확보했지만 실측 cache hit률 미확인. cost 모니터링 필요

### 외부 의존성 (외부 작업 필요)
6. **UC2 품질 게이트 expert sign-off** — 대구교육대학교 수학교육 전문가가 `evals/issue-28/golden_sessions.example.json` 라벨 정제 필요. `--live` 실행 시 strengths recall ≥ 70%, alt_q rubric ≥ 3.0/5 통과 후 `docs/issue-28/expert-review.md`에 sign-off 기록

---

## 4. 핵심 파일 (Files)

### 신규 (28개)
**데이터 레이어:**
- `src/db/migrations/019_add_session_feedback_report.sql` (+ down)
- `src/db/migrations/020_add_api_usage_operation.sql` (+ down)
- `src/db/migrations/021_add_ui_event.sql` (+ down)
- `src/models/session_feedback_report.py`
- `src/models/ui_event.py`

**서비스 + 유틸:**
- `src/prompts/session_synthesis_prompt.txt` (1511 token stable prefix)
- `src/services/session_synthesizer.py`
- `src/utils/session_feedback.py`

**프론트엔드:**
- `static/js/analysis-toggle.js`

**테스트 (13개):**
- `tests/unit/test_session_synthesizer.py`, `test_session_feedback_utils.py`, `test_prompt_hash.py`, `test_sqlite_pragma.py`
- `tests/integration/test_migration_019.py`, `test_migration_020.py`, `test_migration_021.py`, `test_analysis_pipeline_e2e.py`, `test_concurrent_analyze.py`, `test_ui_event_logging.py`
- `tests/api/test_analysis_report_endpoint.py`, `test_regenerate_endpoint.py`
- `tests/contract/test_csv_export_regression.py`, `test_admin_api_plain_feedback.py`
- `tests/templates/test_analysis_modal_states.py`

**문서/평가:**
- `docs/issue-28/expert-review.md`
- `docs/issue-28/HANDOFF.md` (이 문서)
- `evals/issue-28/schemas.py`, `rubric.md`, `eval_synthesis.py`, `golden_sessions.example.json`, `tests/`

### 수정 (15개)
- `CHANGELOG.md` — Unreleased entry 추가
- `pyproject.toml` — ruff config (N999 ignore for evals/issue-28)
- `src/api/routes/admin_session_actions.py` (+208) — regenerate endpoint
- `src/api/routes/session_analysis.py` (+74) — feedback_status, feedback_sections, stats, detail-opened
- `src/db/init_schema.py` (+34) — 새 테이블 fresh-install
- `src/models/__init__.py`, `api_usage.py`, `session.py`, `user.py`
- `src/services/analysis_pipeline.py` (+202) — LLM-first, parallel classify, 통합 duplicate handler
- `src/templates/analysis.html` (+250-84) — full page wedge
- `src/templates/layout.html` (+1)
- `src/templates/partials/analysis_modal.html` (+288-100) — wedge 4상태
- `static/css/styles.css` (+123) — `/* Issue #28 — Analysis Report Wedge */` 섹션
- `tests/conftest.py` (+206) — synthesis_mock, authenticated client, PRAGMA fixtures

---

## 5. 남은 작업 (Remaining)

### 필수 (PR 머지 전)
- [ ] **회귀 fix 3 파일**: `tests/integration/test_framework_delete.py`, `tests/unit/test_message_updates.py`, `tests/integration/test_full_dialogue_flow.py` — manual row insert를 컴포지트 fixture로 교체
- [ ] **ruff --fix on 신규 issue #28 파일** (32 errors, 15 자동 fix 가능, 17은 수동 검토)
- [ ] **CSV snapshot 첫 생성** — `tests/contract/test_csv_export_regression.py` 첫 실행 시 `tests/contract/snapshots/csv_user_export.sha256` 생성
- [ ] **전체 pytest green 재확인** (현재 8 failed + 14 errors → 0/0 목표)
- [ ] **commit 분할 (Stage A-F별로 atomic commit)** + PR 작성

### 권장 (후속 이슈)
- [ ] phase 2 탭 UI (engagement metric ≥ 40% 검증 후)
- [ ] Alembic 도입 (별도 infrastructure 이슈)
- [ ] 202+poll 비동기 패턴 (retry storm > 1% 시)
- [ ] 강사 대시보드 / cohort 분석
- [ ] OpenAI prompt cache hit률 모니터링 + 필요 시 prefix 재배치

### 외부 (사용자/조직 작업)
- [ ] 대구교육대학교 수학교육 전문가 골든 셋 라벨 정제 (UC2 quality gate prerequisite)
- [ ] `python evals/issue-28/eval_synthesis.py --live` 실행 + scorecard 검토
- [ ] `docs/issue-28/expert-review.md`에 sign-off 기록

---

## 6. 팀 운영 회고

**잘 된 점:**
- Plan v2.2가 명확한 명세 → 워커들이 큰 추측 없이 작업
- worker-1-3의 Stage D fix는 4가지 진단을 받아 17 fail → 17 pass 깔끔하게 해결
- worker-2-2의 Stage C E9 prefix 수정 (506 → 1511 tokens) 원샷 성공
- worker-3가 block 상태에서도 사전 작업 → 시간 단축
- Phase 4 verification에서 회귀 발견됨 (전체 pytest 실행 덕분)

**개선 필요:**
- 세션 재시작 시 워커 stale → 재스폰 + Task owner 수동 업데이트 패턴 반복 (`-2`, `-3` suffix)
- 워커들이 "단위 테스트만 보고 완료 신고" — 전체 회귀 테스트 미실행 → 회귀가 Phase 4까지 노출 안 됨. 워커 verification gate에 `pytest tests/` 강제 필요
- `ruff --fix` 워커 verification gate 누락 → 32개 신규 코드 ruff error 잔존
- worker-3 (원본)의 사전 작업이 Stage D 완료 시점에 자동으로 final test로 연결되지 않음 — 수동 worker-3-2 spawn 필요

---

## 7. 재시작 시 컨텍스트 복구

새 세션이 이 작업을 이어받을 경우:
```bash
# 1. 브랜치 확인
git branch --show-current  # feat/issue-28-analysis-report-redesign

# 2. plan + test plan 읽기
cat ~/.gstack/projects/DomineYH-misconcept_platform/dominelinux-feat-issue-28-analysis-report-redesign-design-20260424-141916.md
cat ~/.gstack/projects/DomineYH-misconcept_platform/dominelinux-feat-issue-28-analysis-report-redesign-test-plan-20260424-141916.md

# 3. 이 핸드오프 읽기
cat docs/issue-28/HANDOFF.md

# 4. 현재 상태 점검
git diff --stat HEAD  # 15 modified
git status --short | grep "^??" | head -30  # 28 new

# 5. 회귀 확인
python -m pytest tests/integration/test_framework_delete.py tests/unit/test_message_updates.py tests/integration/test_full_dialogue_flow.py --tb=line -q

# 6. ruff 잔존 errors
ruff check src/services/session_synthesizer.py src/services/analysis_pipeline.py src/utils/session_feedback.py src/api/routes/session_analysis.py src/api/routes/admin_session_actions.py src/models/session_feedback_report.py src/models/ui_event.py tests/contract/ tests/templates/ tests/integration/test_analysis_pipeline_e2e.py tests/integration/test_concurrent_analyze.py tests/integration/test_migration_019.py tests/integration/test_migration_020.py tests/integration/test_migration_021.py tests/integration/test_ui_event_logging.py tests/api/test_analysis_report_endpoint.py tests/api/test_regenerate_endpoint.py tests/unit/test_session_synthesizer.py tests/unit/test_session_feedback_utils.py tests/unit/test_prompt_hash.py tests/unit/test_sqlite_pragma.py
```

---

_Generated by team-lead@issue-28-wedge after completion of all 7 stages._
