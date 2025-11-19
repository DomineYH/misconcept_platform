# Database Migration Guidelines

## 개요

본 문서는 스키마 마이그레이션 작성 및 리뷰 가이드라인을 정의한다.
Migration 003의 실수(시나리오 오버라이드 컬럼 제거)를 교훈으로
스키마-코드 불일치를 사전에 방지하기 위한 체크리스트를 제공한다.

## Migration 번호 규칙

- **001-099**: 초기 개발 및 피처 추가
- **100-199**: 스키마 리팩토링
- **200-299**: 성능 최적화
- **900-999**: 긴급 핫픽스 (예: 006 → 900번대 롤백)

## Migration 작성 프로세스

### 1단계: 변경 계획 수립
**도구**: 노트, 다이어그램 도구

**체크리스트**:
- [ ] 변경 목적이 명확한가? (피처 추가/제거/리팩토링)
- [ ] 영향받는 테이블/컬럼 목록 작성
- [ ] ORM 모델 변경 범위 파악
- [ ] 데이터 마이그레이션 전략 수립 (기존 데이터 처리 방법)

**출력**: `modify/migration_NNN_plan.md`

### 2단계: ORM 모델 Diff 분석
**도구**: `git diff`, 텍스트 편집기

**체크리스트**:
- [ ] ORM 모델 파일(`src/models/*.py`) 변경사항 확인
- [ ] 추가/삭제/변경된 컬럼 목록화
- [ ] 타입/제약조건 변경사항 문서화
- [ ] 외래키/관계 변경사항 확인

**명령어 예시**:
```bash
# ORM 모델 변경사항 확인
git diff src/models/scenario.py

# 전체 모델 파일 변경사항
git diff src/models/
```

**출력**: 컬럼 변경 목록 (추가/삭제/수정)

### 3단계: 코드베이스 참조 검색
**도구**: `ripgrep` (rg)

**체크리스트**:
- [ ] 제거할 컬럼명으로 전체 검색
- [ ] 변경할 컬럼명으로 전체 검색
- [ ] 영향받는 파일 목록 작성 (경로, 라인 번호 포함)
- [ ] 템플릿/프론트엔드 코드도 검색

**명령어 예시**:
```bash
# 제거할 컬럼 참조 검색 (Migration 003 예시)
rg -n "chat_model|chat_temperature|tutor_enabled|tutor_intervention_threshold" src/ tests/

# 특정 컬럼 단독 검색
rg -n "chat_model" src/ tests/ templates/

# JSON/설정 파일도 검색
rg -n "chat_model" --type-add 'config:*.{json,yaml,toml}' -t config
```

**출력**: `modify/migration_NNN_affected_files.md`

**예시 출력**:
```
src/models/scenario.py:46: chat_model: Mapped[Optional[str]]
src/services/student_bot.py:23: model = scenario.chat_model or default
tests/unit/test_scenario.py:15: assert scenario.chat_model == "gpt-4"
```

### 4단계: Migration SQL 작성
**도구**: 텍스트 편집기, SQLite CLI

**체크리스트**:
- [ ] 파일명: `NNN_descriptive_name.sql` 형식
- [ ] 헤더 주석 포함 (목적, 날짜, 이유)
- [ ] `BEGIN TRANSACTION` / `COMMIT` 사용
- [ ] SQLite 제약사항 고려 (ALTER TABLE 제한)
- [ ] 인덱스 재생성 포함
- [ ] 롤백 절차 주석으로 명시

**SQLite 제약사항**:
- `DROP COLUMN` 미지원 → 테이블 재생성 필요
- `ALTER COLUMN` 미지원 → 테이블 재생성 필요
- 테이블 재생성 시 인덱스/외래키도 재생성 필수

**템플릿**:
```sql
-- Migration NNN: [변경 내용 한줄 요약]
-- Date: YYYY-MM-DD
-- Purpose: [상세 목적]
-- Background: [맥락/이유]
-- Changes: [변경 목록]

BEGIN TRANSACTION;

-- [SQL 문들]

COMMIT;

-- ============================================
-- Verification queries (run after migration)
-- ============================================
-- [검증 쿼리]

-- ============================================
-- Rollback procedure (if needed)
-- ============================================
-- [롤백 절차]
```

**출력**: `src/db/migrations/NNN_name.sql`

### 5단계: init_schema.py 동기화
**도구**: 텍스트 편집기

**체크리스트**:
- [ ] `src/db/init_schema.py` 파일 열기
- [ ] 해당 테이블 `CREATE TABLE` 구문 찾기
- [ ] Migration SQL과 동일하게 컬럼 추가/제거/수정
- [ ] 제약조건(`CHECK`, `FOREIGN KEY`) 동기화
- [ ] 인덱스 `CREATE INDEX` 동기화

**명령어 예시**:
```bash
# init_schema.py에서 테이블 정의 찾기
rg -n "CREATE TABLE.*scenario" src/db/init_schema.py

# 특정 컬럼 존재 확인
rg -n "chat_model" src/db/init_schema.py
```

**주의사항**:
- ORM 모델 → Migration SQL → init_schema.py 순서로 3곳 모두 동기화
- 컬럼 순서는 일관성 유지 (가독성)
- 주석도 3곳 모두 동일하게 작성

### 6단계: 로컬 테스트
**도구**: SQLite CLI, pytest

**체크리스트**:
- [ ] 현재 DB 백업 생성
- [ ] Migration SQL 실행
- [ ] `PRAGMA table_info(테이블명)` 로 스키마 확인
- [ ] 데이터 무결성 확인 (레코드 수, 샘플 쿼리)
- [ ] ORM 모델 로드 테스트 (pytest)
- [ ] 관련 API 엔드포인트 테스트

**명령어 예시**:
```bash
# 1. 백업 생성
cp dialogue_sim.db dialogue_sim.db.backup_$(date +%Y%m%d_%H%M%S)

# 2. Migration 실행
sqlite3 dialogue_sim.db < src/db/migrations/NNN_name.sql

# 3. 스키마 확인
sqlite3 dialogue_sim.db "PRAGMA table_info(scenario);"

# 4. 데이터 확인
sqlite3 dialogue_sim.db "SELECT COUNT(*) FROM scenario;"
sqlite3 dialogue_sim.db "SELECT * FROM scenario LIMIT 3;"

# 5. ORM 테스트
pytest tests/unit/test_scenario.py -v

# 6. API 테스트
pytest tests/integration/test_scenario_routes.py -v
```

**기대 결과**:
- 모든 컬럼이 ORM 모델과 일치
- 기존 데이터 보존 (레코드 수 동일)
- pytest 전부 통과
- API 응답 정상

### 7단계: 테스트 코드 업데이트
**도구**: pytest, 텍스트 편집기

**체크리스트**:
- [ ] 제거된 컬럼 참조하는 테스트 수정/제거
- [ ] 추가된 컬럼 테스트 케이스 작성
- [ ] 픽스처(fixture) 업데이트
- [ ] 모든 테스트 통과 확인

**명령어 예시**:
```bash
# 특정 컬럼 참조하는 테스트 검색
rg -n "chat_model" tests/

# 테스트 실행
pytest tests/ -v

# 특정 모델 테스트만 실행
pytest tests/unit/test_scenario.py::test_scenario_creation -v
```

### 8단계: 문서화
**도구**: Markdown 편집기

**체크리스트**:
- [ ] Migration 파일 상단 주석 작성 완료
- [ ] 롤백 절차 명시
- [ ] CHANGELOG.md 업데이트 (있는 경우)
- [ ] 리뷰어에게 전달할 체크리스트 준비

**출력**: Migration 파일 헤더, CHANGELOG 엔트리

---

## Migration 리뷰 체크리스트

리뷰어가 PR 검토 시 사용하는 체크리스트:

### 필수 확인 항목

#### 1. ORM 일치성
- [ ] ORM 모델 변경사항과 Migration SQL 일치하는가?
- [ ] 컬럼 타입, 제약조건, 기본값이 동일한가?
- [ ] 외래키 관계가 정확한가?

**검증 방법**:
```bash
# ORM 모델 확인
cat src/models/scenario.py

# Migration SQL 확인
cat src/db/migrations/NNN_name.sql

# Diff 비교
diff <(rg "mapped_column" src/models/scenario.py) \
     <(rg "CREATE TABLE scenario" -A 30 src/db/migrations/NNN_name.sql)
```

#### 2. init_schema.py 동기화
- [ ] `init_schema.py`도 동일하게 업데이트되었는가?
- [ ] 인덱스 정의도 포함되었는가?

**검증 방법**:
```bash
# init_schema.py 확인
rg -A 30 "CREATE TABLE.*scenario" src/db/init_schema.py
```

#### 3. 코드 참조 완전성
- [ ] 제거된 컬럼 참조가 코드베이스에 남아있지 않은가?
- [ ] 템플릿/JS 파일도 확인했는가?

**검증 방법**:
```bash
# 전체 코드베이스 검색
rg -n "제거된_컬럼명" src/ tests/ templates/ static/
```

#### 4. 데이터 마이그레이션
- [ ] 기존 데이터 보존 로직이 있는가? (INSERT SELECT)
- [ ] NULL 허용 여부가 적절한가?
- [ ] 기본값이 비즈니스 로직에 부합하는가?

**검증 방법**:
```bash
# Migration SQL에서 데이터 복사 구문 확인
rg "INSERT INTO.*SELECT" src/db/migrations/NNN_name.sql
```

#### 5. 트랜잭션 안전성
- [ ] `BEGIN TRANSACTION` / `COMMIT` 사용했는가?
- [ ] 인덱스 드롭/재생성 순서가 맞는가?

**검증 방법**:
```bash
# 트랜잭션 구문 확인
rg "BEGIN TRANSACTION|COMMIT" src/db/migrations/NNN_name.sql
```

#### 6. 롤백 가능성
- [ ] 롤백 절차가 문서화되어 있는가?
- [ ] 백업 생성 가이드가 있는가?

**검증 방법**:
```bash
# 롤백 절차 주석 확인
rg "Rollback|rollback" src/db/migrations/NNN_name.sql
```

#### 7. 테스트 커버리지
- [ ] 관련 테스트가 업데이트되었는가?
- [ ] pytest가 전부 통과하는가?

**검증 방법**:
```bash
# 테스트 실행
pytest tests/ -v --tb=short
```

### 선택 확인 항목

#### 8. 성능 영향
- [ ] 인덱스가 적절하게 설정되었는가?
- [ ] 대용량 테이블인 경우 마이그레이션 시간 측정했는가?

#### 9. 보안 고려사항
- [ ] 민감한 데이터 컬럼에 적절한 제약조건이 있는가?
- [ ] 외래키 무결성이 보장되는가?

---

## Migration 실행 절차 (Production)

### 사전 준비
1. **백업 생성**:
   ```bash
   cp dialogue_sim.db dialogue_sim.db.backup_pre_migration_NNN
   ```

2. **백업 검증**:
   ```bash
   sqlite3 dialogue_sim.db.backup_pre_migration_NNN "SELECT COUNT(*) FROM scenario;"
   ```

3. **다운타임 계획**: 필요 시 서비스 중지

### 실행
1. **Migration 적용**:
   ```bash
   sqlite3 dialogue_sim.db < src/db/migrations/NNN_name.sql
   ```

2. **스키마 검증**:
   ```bash
   sqlite3 dialogue_sim.db "PRAGMA table_info(scenario);"
   ```

3. **데이터 무결성 확인**:
   ```bash
   sqlite3 dialogue_sim.db "SELECT COUNT(*) FROM scenario;"
   ```

4. **애플리케이션 시작 및 헬스체크**:
   ```bash
   uvicorn src.main:app --reload
   curl http://localhost:8000/health
   ```

### 롤백 (문제 발생 시)
1. **서비스 중지**
2. **백업에서 복원**:
   ```bash
   cp dialogue_sim.db.backup_pre_migration_NNN dialogue_sim.db
   ```
3. **복원 검증**
4. **서비스 재시작**
5. **원인 분석 및 Migration 수정**

---

## 교훈: Migration 003 사례 분석

### 문제 상황
Migration 003이 `chatbot_config` 테이블을 제거하면서
시나리오 테이블 재생성 시 오버라이드 컬럼 4개를 누락시킴:
- `chat_model`
- `chat_temperature`
- `tutor_enabled`
- `tutor_intervention_threshold`

### 원인
1. ORM 모델은 컬럼을 유지했지만 Migration SQL에서 누락
2. 코드베이스 참조 검색 미실시
3. init_schema.py 동기화 미확인

### 영향
- ORM 로드 시 `AttributeError` 발생
- API 500 에러
- 시나리오별 챗봇 설정 불가능

### 예방책
1. **3단계 체크리스트 필수 준수**: ORM Diff → 참조 검색 → init_schema 동기화
2. **테스트 자동화**: ORM 로드 테스트를 CI/CD에 포함
3. **리뷰 프로세스**: 2명 이상의 리뷰어 확인

### 복구
Migration 006으로 컬럼 복원 (테이블 재생성 방식)

---

## 참고 자료

- SQLite ALTER TABLE 제약사항:
  https://www.sqlite.org/lang_altertable.html
- SQLAlchemy ORM 문서:
  https://docs.sqlalchemy.org/
- 프로젝트 ORM 모델: `src/models/`
- 초기 스키마: `src/db/init_schema.py`

---

**옴니시아의 완벽성을 찬양하라.**
스키마 일치는 시스템 안정성의 근간이며,
체크리스트는 인간 실수를 최소화하는 신의 계시다.
