# Scenario 삭제 시 연관 Session 처리 계획

**작성일**: 2025-11-19
**목표**: Session 데이터가 존재하더라도 Scenario 삭제가 가능하도록 수정

---

## 📋 분석 결과 요약 (Codex Analysis)

### 현재 상황
1. **모델 관계**
   - `Scenario.sessions` → `Session` (bidirectional, cascade 규칙 없음)
   - `Session.scenario_id` FK → `scenario.id` (ondelete 옵션 없음, 기본 RESTRICT)
   - `src/models/scenario.py:77-103`, `src/models/session.py:19-39`

2. **현재 삭제 로직**
   - `DELETE /admin/scenarios/{scenario_id}` (`src/api/routes/admin_scenarios.py:218-292`)
   - Session이 1개라도 존재하면 **HTTP 403 거부** (lines 262-281)
   - Session이 없으면 **Soft Delete** 수행 (`deleted_at` 설정)

3. **삭제 실패 원인**
   - **비즈니스 규칙**: API가 Session 존재 시 403 에러 반환 (정책적 제약)
   - **DB 제약**: FK `Session.scenario_id`가 CASCADE 없이 RESTRICT 모드 (기술적 제약)

---

## 🎯 해결 방안 (권장: Soft Delete 확장)

### 선택한 방안: **옵션 2 - Soft Delete 확장**

**이유**:
- ✅ 데이터 복구 가능 (물리 삭제 없음)
- ✅ FK 제약 조건 위반 없음
- ✅ 감사(Audit) 추적 가능
- ✅ 기존 soft delete 패턴과 일관성 유지

**대안 방안**:
- **옵션 1 - Cascade Delete (Hard Delete)**: 데이터 영구 손실, 복구 불가
- **옵션 3 - Manual Cleanup**: 복잡도 증가, 관리 부담

---

## 📝 구체적 수정 계획

### Step 1: Session 모델에 Soft Delete 지원 추가

**파일**: `src/models/session.py`

**변경 내용**:
```python
# 추가할 컬럼
deleted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)

# 추가할 메서드
def mark_deleted(self) -> None:
    """Mark session as soft-deleted with UTC timestamp."""
    self.deleted_at = datetime.utcnow()
```

**참고**: `Scenario.mark_deleted()` 패턴 참조 (`src/models/scenario.py:121-123`)

---

### Step 2: 데이터베이스 마이그레이션 작성

**파일**: `src/db/migrations/010_add_session_soft_delete.sql`

**내용**:
```sql
-- Migration 010: Add soft delete support to session table
-- Author: [Your Name]
-- Date: 2025-11-19
-- Purpose: Enable soft delete for sessions when scenarios are deleted

-- Add deleted_at column
ALTER TABLE session ADD COLUMN deleted_at TIMESTAMP NULL;

-- Create index for soft delete queries (performance)
CREATE INDEX IF NOT EXISTS idx_session_deleted ON session(deleted_at);

-- Verification: Check schema
-- PRAGMA table_info(session);
```

**실행 방법**:
```bash
sqlite3 dialogue_sim.db < src/db/migrations/010_add_session_soft_delete.sql
./src/db/migrations/verify_migration.sh
```

---

### Step 3: DELETE API 로직 수정

**파일**: `src/api/routes/admin_scenarios.py`

**현재 로직** (lines 262-281):
```python
# 현재: Session 존재 시 403 에러
if active_count > 0 or completed_count > 0:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Cannot delete scenario {scenario_id}: ..."
    )
```

**수정 후 로직**:
```python
# 수정: Session도 함께 soft delete
# 1. 연관된 모든 Session 조회 (deleted_at IS NULL)
sessions = await db.execute(
    select(Session).where(
        Session.scenario_id == scenario_id,
        Session.deleted_at.is_(None)
    )
)
sessions = sessions.scalars().all()

# 2. 각 Session을 soft delete
for session in sessions:
    session.mark_deleted()

# 3. Scenario를 soft delete
scenario.mark_deleted()

# 4. 커밋
await db.commit()

logger.info(
    f"Soft deleted scenario {scenario_id} "
    f"and {len(sessions)} related sessions"
)
```

**참고**:
- Message와 ApiUsageLog는 이미 Session에 cascade 설정됨 (`src/models/session.py:40-53`)
- Session만 soft delete하면 하위 데이터는 자동 처리됨

---

### Step 4: 쿼리 필터 수정 (deleted_at 필터 추가)

**영향 받는 파일**:
1. **`src/api/routes/admin_sessions.py`**
   - `GET /admin/sessions` - Session 목록 조회
   - 필터 추가: `.where(Session.deleted_at.is_(None))`

2. **`src/api/routes/sessions.py`**
   - `GET /sessions/{session_id}/messages` - 메시지 조회
   - 필터 추가: Session 로드 시 `deleted_at IS NULL` 검증

3. **`src/services/session_mgr.py`**
   - `create_session()`, `get_session()` 등 모든 Session 조회 로직
   - 필터 추가: `.where(Session.deleted_at.is_(None))`

**수정 예시**:
```python
# Before
result = await db.execute(select(Session).where(Session.id == session_id))

# After
result = await db.execute(
    select(Session).where(
        Session.id == session_id,
        Session.deleted_at.is_(None)  # 삭제되지 않은 것만
    )
)
```

---

### Step 5: init_schema.py 동기화

**파일**: `src/db/init_schema.py`

**추가 내용**:
```sql
CREATE TABLE IF NOT EXISTS session (
    ...
    deleted_at TIMESTAMP NULL,  -- 추가
    ...
);

CREATE INDEX IF NOT EXISTS idx_session_deleted ON session(deleted_at);  -- 추가
```

**참고**: `Scenario` 테이블의 `deleted_at` 컬럼 정의 참조

---

### Step 6: 테스트 작성

**파일**: `tests/integration/test_scenario_delete.py` (신규 생성)

**테스트 케이스**:
1. **Session이 있는 Scenario 삭제 성공**
   - Given: Scenario에 2개의 Session 연결
   - When: DELETE /admin/scenarios/{id} 호출
   - Then:
     - HTTP 200 반환
     - Scenario.deleted_at 설정됨
     - 2개의 Session.deleted_at 설정됨

2. **Soft Deleted Session은 조회 불가**
   - Given: Soft deleted Session
   - When: GET /admin/sessions 호출
   - Then: 해당 Session이 목록에 나타나지 않음

3. **Scenario 삭제 후 Message 접근 불가**
   - Given: Soft deleted Session
   - When: GET /sessions/{session_id}/messages 호출
   - Then: HTTP 404 반환

**테스트 코드 예시**:
```python
async def test_delete_scenario_with_sessions(client, db_session):
    """Test scenario deletion with related sessions."""
    # Setup
    scenario = await create_test_scenario(db_session)
    session1 = await create_test_session(db_session, scenario.id)
    session2 = await create_test_session(db_session, scenario.id)

    # Execute
    response = client.delete(f"/admin/scenarios/{scenario.id}")

    # Assert
    assert response.status_code == 200

    # Verify soft delete
    await db_session.refresh(scenario)
    await db_session.refresh(session1)
    await db_session.refresh(session2)

    assert scenario.deleted_at is not None
    assert session1.deleted_at is not None
    assert session2.deleted_at is not None
```

---

### Step 7: 기존 테스트 수정

**영향 받는 테스트**:
- `tests/contract/test_session_endpoints.py`
- `tests/integration/test_scenario_management.py`

**수정 이유**:
- 기존 테스트는 "Session 있으면 403" 가정
- 새 로직은 "Session 있어도 200 반환 (soft delete)"

**수정 예시**:
```python
# Before
assert response.status_code == 403
assert "Cannot delete" in response.json()["detail"]

# After
assert response.status_code == 200
# Verify sessions are soft deleted
sessions = await db.execute(
    select(Session).where(Session.scenario_id == scenario_id)
)
for session in sessions.scalars():
    assert session.deleted_at is not None
```

---

## 🔍 검증 체크리스트

### 마이그레이션 검증
- [ ] `sqlite3 dialogue_sim.db "PRAGMA table_info(session);"` - deleted_at 컬럼 존재 확인
- [ ] `./src/db/migrations/verify_migration.sh` - 스크립트 실행
- [ ] `pytest tests/contract/test_schema_integrity.py -v` - 스키마 무결성 검증

### 기능 검증
- [ ] Session이 있는 Scenario 삭제 성공 (HTTP 200)
- [ ] Soft deleted Session이 목록에서 제외됨
- [ ] Soft deleted Session의 메시지 접근 불가 (HTTP 404)
- [ ] Message와 ApiUsageLog는 여전히 데이터베이스에 존재 (물리 삭제 안 됨)

### 회귀 테스트
- [ ] `pytest tests/ -v` - 전체 테스트 통과
- [ ] 기존 Scenario 생성/수정/조회 기능 정상 동작
- [ ] Admin 대시보드에서 Scenario 목록 정상 표시

---

## 📊 영향 받는 파일 목록

### 수정 필요 파일 (7개)
1. **`src/models/session.py`** - deleted_at 컬럼 및 mark_deleted() 추가
2. **`src/db/migrations/010_add_session_soft_delete.sql`** - 신규 마이그레이션
3. **`src/db/init_schema.py`** - Session 테이블 스키마 동기화
4. **`src/api/routes/admin_scenarios.py`** - DELETE 로직 수정 (403 제거, soft delete 추가)
5. **`src/api/routes/admin_sessions.py`** - Session 조회 필터 추가
6. **`src/api/routes/sessions.py`** - Session 메시지 조회 필터 추가
7. **`src/services/session_mgr.py`** - 모든 Session 조회 로직 필터 추가

### 신규 생성 파일 (1개)
8. **`tests/integration/test_scenario_delete.py`** - Scenario 삭제 통합 테스트

### 수정 필요 테스트 (2개)
9. **`tests/contract/test_session_endpoints.py`** - 403 → 200 변경
10. **`tests/integration/test_scenario_management.py`** - 삭제 검증 로직 변경

---

## ⚠️ 주의 사항

### 데이터베이스 백업
```bash
# 마이그레이션 전 필수 백업
cp dialogue_sim.db dialogue_sim.db.backup_pre_migration_010
```

### 롤백 전략
```sql
-- 마이그레이션 롤백 (필요 시)
DROP INDEX IF EXISTS idx_session_deleted;
ALTER TABLE session DROP COLUMN deleted_at;
```

### 성능 고려사항
- `idx_session_deleted` 인덱스로 `WHERE deleted_at IS NULL` 쿼리 최적화
- Session 수가 많은 경우 (1000+) 배치 삭제 고려

---

## 📅 구현 순서

1. **Phase 1: 준비**
   - [ ] 데이터베이스 백업
   - [ ] Session 모델 수정 (deleted_at 추가)
   - [ ] 마이그레이션 파일 작성

2. **Phase 2: 마이그레이션**
   - [ ] 마이그레이션 실행
   - [ ] init_schema.py 동기화
   - [ ] 스키마 무결성 검증

3. **Phase 3: API 로직 수정**
   - [ ] DELETE 엔드포인트 수정 (403 제거)
   - [ ] Session 조회 필터 추가 (3개 파일)
   - [ ] 로깅 추가

4. **Phase 4: 테스트**
   - [ ] 신규 통합 테스트 작성
   - [ ] 기존 테스트 수정
   - [ ] 전체 테스트 실행 (`pytest tests/ -v`)

5. **Phase 5: 검증**
   - [ ] 수동 테스트 (Postman/cURL)
   - [ ] Admin UI 동작 확인
   - [ ] 로그 확인

---

## 🔗 참고 자료

- **Codex 분석 보고서**: Session ID `019a9c08-db67-78c3-b27a-d24e2394eef5`
- **관련 문서**:
  - `src/db/migrations/README.md` - 마이그레이션 가이드
  - `src/db/migrations/009_add_scenario_soft_delete.sql` - Scenario soft delete 참조
  - `CLAUDE.md` - 프로젝트 개발 가이드라인

---

## ✅ 완료 기준

1. ✅ Session이 있는 Scenario 삭제 시 HTTP 200 반환
2. ✅ Scenario와 연관된 모든 Session이 soft delete됨
3. ✅ Soft deleted Session/Message가 API에서 조회 불가
4. ✅ 전체 테스트 통과 (pytest 100%)
5. ✅ 마이그레이션 문서화 완료
6. ✅ 코드 리뷰 승인

---

**작성자**: Claude (Codex Analysis)
**검토자**: [To Be Assigned]
**승인자**: [To Be Assigned]
