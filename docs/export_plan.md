# Admin Scenario CSV Export Plan (Option B)

## 목표

관리자 화면의 **시나리오 목록**에서 각 시나리오의 **대화(세션) 목록**으로 이동하고,
- **특정 사용자(교사)** 또는 **전체 사용자(교사)** 의 대화를 선택/필터링하여
- **CSV로 다운로드**할 수 있게 한다.

## 확정 요구사항

| 항목 | 결정 |
|------|------|
| 교사 식별자 | `teacher_id`, `teacher_nickname`, `teacher_student_uid` 모두 포함 |
| 닉네임 | 표시/저장 대상 (익명화 X) |
| 분석 메타데이터 | `QuestionAnalysis.meta_json` 포함 |
| 세션 범위 | **종료된 세션만 포함** (`Session.ended_at IS NOT NULL`) |

## 현 상태 (기존 기능)

### 단일 세션 CSV (교사용)
- **경로**: `GET /sessions/{session_id}/export.csv`
- **특징**: 익명 해시(`student_hash`) 포함, 본인 세션만 접근 가능
- **코드**: `src/api/routes/sessions.py:744` / `src/services/export.py`

### 관리자 대량 CSV
- **경로**: `GET /admin/sessions/export`
- **현재 상태**: `scenario_id`만 필터 지원, 익명 해시 기반
- **코드**: `src/api/routes/admin_sessions.py:122` / `src/services/export.py`

### 관리자 세션 목록 페이지
- **경로**: `GET /admin/sessions-page`
- **템플릿**: `src/templates/admin/sessions.html`
- **현재 상태**: 시나리오 필터 + "CSV 내보내기" 링크만 존재

## B안 UX 설계

### 1) 시나리오 목록 → 대화목록 진입

`src/templates/admin/scenarios.html`의 각 시나리오 카드에 버튼 추가:

```
[대화목록] → /admin/sessions-page?scenario_id={scenario_id}
```

### 2) 대화목록(세션 목록)에서 선택/필터 후 다운로드

`/admin/sessions-page`에서 제공:

**필터 옵션**
- 시나리오 (기존)
- 교사 (`teacher_id` 선택 또는 `student_uid`/`nickname` 검색)
- 기간 (`date_from` / `date_to`)
- "종료 세션만" (기본 ON, export는 강제)

**다운로드 액션**
- "필터 전체 CSV 다운로드" - 현재 필터 조건 전체
- "선택 CSV 다운로드" - 체크박스로 선택한 세션만

## CSV 스키마 (관리자용, 신규)

기본 원칙: **메시지 단위 row** + **세션 요약 row (선택)**

### 컬럼 정의

| 컬럼명 | 설명 | 비고 |
|--------|------|------|
| `session_id` | 세션 ID | |
| `scenario_id` | 시나리오 ID | |
| `scenario_title` | 시나리오 제목 | |
| `teacher_id` | 교사 ID | |
| `teacher_student_uid` | 교사 학생ID | |
| `teacher_nickname` | 교사 닉네임 | |
| `session_started_at` | 세션 시작 시간 | ISO 8601 |
| `session_ended_at` | 세션 종료 시간 | ISO 8601 |
| `message_id` | 메시지 ID | |
| `message_created_at` | 메시지 생성 시간 | ISO 8601 |
| `role` | 발화자 역할 | teacher/student/tutor/summary |
| `content` | 메시지 내용 | |
| `label` | 분석 라벨 | teacher 메시지만 |
| `confidence` | 분석 신뢰도 | teacher 메시지만 |
| `meta_json` | 분석 상세 JSON | teacher 메시지만 |
| `feedback` | 세션 피드백 | summary row에만 |

### 주의사항
- `meta_json`은 JSON 문자열이므로 CSV에서 자동 quoting 유지
- 기존 교사용 CSV(익명화)는 그대로 유지, 관리자용은 별도 경로로 분리

## 백엔드 설계

### 1) 세션 목록 HTML (기존 확장)

**경로**: `GET /admin/sessions-page`

**변경사항**:
- 필터 파라미터 확장: `scenario_id`, `teacher_id`, `date_from`, `date_to`
- 목록에 "종료 여부" 표시 + 체크박스 추가
- 교사 목록(distinct teachers) 전달

### 2) 관리자 CSV: 필터 전체 다운로드 (기존 경로 확장)

**경로**: `GET /admin/sessions/export`

**입력 파라미터**:
```
scenario_id: Optional[int]
teacher_id: Optional[int]
date_from: Optional[str]  # ISO 8601
date_to: Optional[str]    # ISO 8601
```

**강제 조건**: `Session.ended_at IS NOT NULL`

**응답**:
- Content-Type: `text/csv; charset=utf-8`
- Header: `Content-Disposition: attachment; filename=sessions_export.csv`

**대용량 대비**: `StreamingResponse` + UTF-8 BOM 옵션

### 3) 관리자 CSV: 선택 다운로드 (신규)

**경로**: `POST /admin/sessions/export-selected`

**입력**: `session_ids` (form 체크박스 다중)

**검증**:
- admin role 확인
- 존재하는 세션만
- **종료 세션만 허용** (active 포함 시 400 에러)

**응답**: CSV attachment

## 서비스 계층 설계

### 파일: `src/services/export.py`

**기존 유지**:
- `CSVExporter.export_session()` - 교사용(익명화)

**신규 추가**:
```python
async def export_session_admin(
    self, session_id: int, db: AsyncSession
) -> str:
    """관리자용 세션 export (raw 교사정보 + meta_json 포함)"""

async def export_multiple_sessions_admin(
    self, session_ids: List[int], db: AsyncSession
) -> str:
    """관리자용 다중 세션 export"""
```

**구현 포인트**:
- `QuestionAnalysis.meta_json`을 teacher 메시지 row에 포함
- `SessionSummary.feedback`는 summary row로 추가

### 성능 최적화 (2단계)

**1차 (기능 완성)**:
- 기존 방식(N+1)으로 빠르게 구현

**2차 (최적화)**:
- bulk query (메시지/분석/요약을 한 번에)
- `StreamingResponse` 본격 적용

## 템플릿 변경

### `src/templates/admin/scenarios.html`

시나리오 카드 액션에 "대화목록" 링크 추가:

```html
<a href="/admin/sessions-page?scenario_id={{ scenario.id }}" 
   class="btn btn-sm btn-secondary">
  대화목록
</a>
```

### `src/templates/admin/sessions.html`

**변경사항**:
- 컬럼 확장: teacher nickname/student_uid, ended_at
- 체크박스 + "선택 CSV 다운로드" form 추가
- 필터 UI 확장: teacher/date

## 테스트 계획

### `tests/contract/test_admin_endpoints.py`

| 테스트 케이스 | 검증 내용 |
|--------------|----------|
| `test_export_sessions_only_ended` | 종료 세션만 포함, active 세션 제외 |
| `test_export_sessions_by_teacher` | `teacher_id` 필터 적용 시 해당 교사 세션만 |
| `test_export_sessions_includes_meta_json` | teacher 메시지에 `meta_json` 컬럼 존재 및 값 포함 |
| `test_export_sessions_includes_teacher_info` | `teacher_nickname`, `teacher_student_uid` 포함 |
| `test_export_selected_sessions` | 선택된 session_ids만 export |
| `test_export_selected_rejects_active` | active 세션 포함 시 400 에러 |

### 기존 테스트 영향

- `tests/integration/test_csv_export.py` - 교사용 익명화 유지, 영향 없음
- `tests/unit/test_export.py` - 기존 메서드 테스트 유지, 신규 메서드 테스트 추가

## 보안/개인정보 주의

- 관리자 CSV에 `teacher_student_uid`가 포함되므로 **개인정보/식별정보로 취급** 필요
- 다운로드 권한: 관리자만 (admin role 확인)
- 접근 로그: 기존 `api_usage` 로그 체계와 연계 검토

## 구현 작업 목록

### Phase 1: 백엔드 (우선순위 높음)

| # | 작업 | 파일 | 예상 시간 |
|---|------|------|----------|
| 1.1 | `export_session_admin()` 메서드 추가 | `src/services/export.py` | 30분 |
| 1.2 | `export_multiple_sessions_admin()` 메서드 추가 | `src/services/export.py` | 20분 |
| 1.3 | `/admin/sessions/export` 필터 확장 | `src/api/routes/admin_sessions.py` | 30분 |
| 1.4 | `/admin/sessions/export-selected` 신규 | `src/api/routes/admin_sessions.py` | 20분 |
| 1.5 | `/admin/sessions-page` 교사 목록 전달 | `src/api/routes/admin_sessions.py` | 15분 |

### Phase 2: 프론트엔드

| # | 작업 | 파일 | 예상 시간 |
|---|------|------|----------|
| 2.1 | 시나리오 카드에 "대화목록" 버튼 추가 | `src/templates/admin/scenarios.html` | 10분 |
| 2.2 | 세션 목록 테이블 확장 (체크박스, 교사정보) | `src/templates/admin/sessions.html` | 30분 |
| 2.3 | 필터 UI 확장 (교사/기간) | `src/templates/admin/sessions.html` | 20분 |
| 2.4 | "선택 CSV 다운로드" JS 로직 | `src/templates/admin/sessions.html` | 20분 |

### Phase 3: 테스트

| # | 작업 | 파일 | 예상 시간 |
|---|------|------|----------|
| 3.1 | 종료 세션 필터 테스트 | `tests/contract/test_admin_endpoints.py` | 20분 |
| 3.2 | 교사 필터 테스트 | `tests/contract/test_admin_endpoints.py` | 15분 |
| 3.3 | meta_json/교사정보 포함 테스트 | `tests/contract/test_admin_endpoints.py` | 20분 |
| 3.4 | 선택 export 테스트 | `tests/contract/test_admin_endpoints.py` | 15분 |
| 3.5 | 신규 서비스 메서드 단위 테스트 | `tests/unit/test_export.py` | 20분 |

### Phase 4: 최적화 (선택)

| # | 작업 | 파일 | 예상 시간 |
|---|------|------|----------|
| 4.1 | bulk query 리팩토링 | `src/services/export.py` | 45분 |
| 4.2 | StreamingResponse + BOM 적용 | `src/api/routes/admin_sessions.py` | 30분 |

**총 예상 시간**: Phase 1-3 약 4시간, Phase 4 약 1.5시간

## 수용 기준 (Definition of Done)

- [ ] 관리자 시나리오 목록에서 각 시나리오의 대화목록으로 이동 가능
- [ ] 대화목록에서 "전체/특정 교사/선택 세션" 단위로 CSV 다운로드 가능
- [ ] CSV에 `teacher_id`, `teacher_student_uid`, `teacher_nickname`, `meta_json` 포함
- [ ] CSV에는 종료 세션 데이터만 포함
- [ ] 관련 contract tests가 필터/종료조건을 검증
- [ ] 기존 교사용 CSV export 기능에 영향 없음

---

**작성일**: 2026-01-03
**버전**: 1.0
