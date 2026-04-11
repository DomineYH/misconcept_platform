# Bulk User Upload — Design Spec

**Date**: 2026-04-11
**Status**: Approved
**Feature**: 사용자 관리에서 CSV 기반 일괄 사용자 추가

## Overview

관리자가 CSV 파일을 통해 다수의 사용자를 한 번에 등록할 수 있는 기능.
업로드 후 미리보기에서 검증 결과를 확인하고, 역할/그룹을 수정한 뒤 최종 등록한다.

## User Flow

```
사용자 관리 페이지
  ├── "CSV 양식 다운로드" → CSV 템플릿 다운로드
  └── "일괄 추가" → 모달 오픈
       ├── Step 1: CSV 파일 업로드
       ├── Step 2: 미리보기 + 편집 (검증, 역할/그룹 지정, 행 추가/수정/삭제)
       └── Step 3: 결과 (성공 N / 실패 N + 실패 사유)
```

## CSV Template

```csv
username,nickname,role,group
```

| Column | Required | Description |
|--------|----------|-------------|
| `username` | Yes | 사용자 ID (영문+숫자+_, 3-50자) |
| `nickname` | Yes | 닉네임 (2-30자) |
| `role` | No | `teacher` or `admin` (기본값: `teacher`) |
| `group` | No | 그룹명 (DB에 등록된 그룹과 매칭, 비어있으면 그룹 없음) |

## API Endpoints

### GET `/admin/users/bulk/template`

CSV 양식 파일을 다운로드한다.

**Response**: `text/csv` 파일 (`bulk_users_template.csv`)

### POST `/admin/users/bulk/preview`

CSV 파일을 업로드하면 파싱 + 검증 후 미리보기 데이터를 반환한다.

**Request**: `multipart/form-data` (file 필드)

**Response** (JSON):
```json
{
  "rows": [
    {
      "row_num": 1,
      "username": "kim_minjun",
      "nickname": "김민준",
      "role": "teacher",
      "group_name": "1학년 1반",
      "group_id": 1,
      "errors": []
    },
    {
      "row_num": 2,
      "username": "admin01",
      "nickname": "관리자일",
      "role": "teacher",
      "group_name": null,
      "group_id": null,
      "errors": ["이미 존재하는 사용자 ID"]
    },
    {
      "row_num": 3,
      "username": "park_jiwoo",
      "nickname": "박지우",
      "role": "teacher",
      "group_name": "3학년 1반",
      "group_id": null,
      "errors": ["존재하지 않는 그룹: 3학년 1반"]
    }
  ],
  "groups": [
    {"id": 1, "name": "1학년 1반"},
    {"id": 2, "name": "1학년 2반"}
  ],
  "summary": {
    "total": 3,
    "valid": 1,
    "error": 2
  }
}
```

**Error responses**:
- `400`: CSV 파싱 실패 (잘못된 파일 형식, 필수 컬럼 누락)
- `400`: 파일 크기 초과 (1MB)
- `400`: 행 수 초과 (100명)

### POST `/admin/users/bulk/register`

검증/수정이 완료된 사용자 목록을 최종 등록한다.

**Request** (JSON):
```json
{
  "users": [
    {
      "username": "kim_minjun",
      "nickname": "김민준",
      "role": "teacher",
      "group_id": 1
    },
    {
      "username": "lee_soyeon",
      "nickname": "이소연",
      "role": "teacher",
      "group_id": 2
    }
  ]
}
```

**Response** (JSON):
```json
{
  "success_count": 2,
  "fail_count": 1,
  "failures": [
    {
      "username": "admin01",
      "nickname": "관리자일",
      "reason": "이미 존재하는 사용자 ID"
    }
  ]
}
```

## Password Policy

- 기본 비밀번호: `00000000` (하드코딩)
- bcrypt 해시 후 저장
- 첫 로그인 시 변경 강제는 이번 범위에 포함하지 않음

## Validation Rules

### CSV 파싱 단계
- 파일 인코딩: UTF-8 우선, EUC-KR 폴백
- 필수 컬럼 존재 확인: `username`, `nickname`
- 최대 파일 크기: 1MB
- 최대 행 수: 100명

### 행 단위 검증 (미리보기)
- `username`: 영문+숫자+_ 만 허용, 3-50자
- `nickname`: 2-30자
- `role`: `teacher` 또는 `admin` (비어있으면 `teacher`, 다른 값은 에러)
- `group`: DB에 등록된 그룹명과 매칭 (없으면 에러 표시, 드롭다운으로 수정 가능)
- DB 내 username 중복 체크
- CSV 내 username 중복 체크 (두 번째부터 에러)

### 등록 단계
- 행 단위 처리: 한 행 실패해도 나머지는 계속 진행 (전체 롤백 X)
- 최종 등록 직전에 username 중복을 한 번 더 확인 (동시 등록 방지)

## UI Design

### 사용자 관리 페이지 헤더
- 기존 "+ 새 사용자" 버튼 왼쪽에 "CSV 양식 다운로드", "일괄 추가" 버튼 추가

### Step 1: 파일 업로드 모달
- 파일 선택 영역 (드래그앤드롭 불필요, 버튼 클릭만)
- CSV 양식 안내 텍스트
- 기본 비밀번호 안내: "기본 비밀번호: 00000000"

### Step 2: 미리보기 테이블
- **상단 일괄 지정 바**: 역할 드롭다운 + 그룹 드롭다운 + "적용" 버튼
- **테이블 컬럼**: #, 사용자 ID, 닉네임, 역할(드롭다운), 그룹(드롭다운), 상태, 작업(삭제)
- **정상 행**: 녹색 체크 "정상"
- **에러 행**: 빨간 배경 + 에러 메시지 (중복 username, 없는 그룹, 유효하지 않은 role 등)
- **에러 그룹 드롭다운**: 에러 상태 표시 + 유효한 그룹 목록으로 수정 가능
- **하단**: "+ 사용자 추가" 버튼 (수동 행 추가)
- **푸터**: 정상 N명 | 에러 N명 | 총 N명 + "취소" / "등록 (N명)" 버튼
- **등록 버튼**: 에러 없는 행 수만 표시, 에러 행은 제외

### Step 3: 결과
- 성공/실패 카드 (큰 숫자 + 라벨)
- 실패 목록 테이블: 사용자 ID, 닉네임, 실패 사유
- "닫기" 버튼 → 사용자 목록 페이지 새로고침

## File Structure

```
src/
├── services/
│   └── admin_user_bulk.py          # NEW: CSV 파싱, 검증, 일괄 등록
├── api/
│   ├── routes/
│   │   └── admin_users.py          # MODIFY: 3개 엔드포인트 추가
│   └── schemas/
│       └── user.py                 # MODIFY: Bulk 관련 스키마 추가
└── templates/
    └── admin/
        └── users.html              # MODIFY: 일괄 추가 모달 UI 추가
```

### New Schemas (`src/api/schemas/user.py`)

```python
class BulkPreviewRow(BaseModel):
    row_num: int
    username: str
    nickname: str
    role: str = "teacher"
    group_name: str | None = None
    group_id: int | None = None
    errors: list[str] = []

class BulkPreviewResponse(BaseModel):
    rows: list[BulkPreviewRow]
    groups: list[dict]  # {id, name}
    summary: dict       # {total, valid, error}

class BulkUserEntry(BaseModel):
    username: str
    nickname: str
    role: str = "teacher"
    group_id: int | None = None

class BulkRegisterRequest(BaseModel):
    users: list[BulkUserEntry]

class BulkFailure(BaseModel):
    username: str
    nickname: str
    reason: str

class BulkRegisterResponse(BaseModel):
    success_count: int
    fail_count: int
    failures: list[BulkFailure]
```

### Service Functions (`src/services/admin_user_bulk.py`)

```python
async def parse_csv(file_content: bytes) -> list[dict]
async def validate_bulk_users(
    rows: list[dict], db: AsyncSession
) -> BulkPreviewResponse
async def register_bulk_users(
    users: list[BulkUserEntry], db: AsyncSession
) -> BulkRegisterResponse
```

## Constraints

- 최대 업로드: 100명/회
- CSV 파일 크기: 1MB 이하
- 인코딩: UTF-8 우선, EUC-KR 폴백
- 기존 User 모델 변경 없음
- 기존 사용자 관리 CRUD에 영향 없음

## Out of Scope

- 첫 로그인 시 비밀번호 변경 강제
- CSV 내보내기 (기존 사용자 목록)
- 일괄 수정/삭제
- 드래그앤드롭 파일 업로드
