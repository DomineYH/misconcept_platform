# SPEC — 오개념 교정 대화 시뮬레이터

## 1. 기술 스택
- 언어/런타임: Python 3.11+(uv 환경에서 구동을 함.)
- 웹 프레임워크: FastAPI (백엔드 API + 서버사이드 렌더링 with Jinja2)
- DB: SQLite3 (SQLAlchemy 2.x ORM)
- 프론트: Jinja 템플릿 + HTMX(부분 갱신) + Tailwind(선택)
- LLM: OpenAI GPT-5(가정) — **대화용 LLM**과 **분석용 LLM** 분리
- 세션/인증: 쿠키 기반 세션 (학생ID+닉네임)

## 2. 도메인 모델 (SQLite 스키마 초안)
```sql
-- 사용자(교사/학생 공용 최소 스키마; 학생 로그인용)
CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_uid TEXT NOT NULL,     -- 학생 고유번호(로그인 키)
  nickname   TEXT NOT NULL,      -- 닉네임(로그인 키)
  role       TEXT NOT NULL CHECK(role IN ('teacher','student','admin')) DEFAULT 'teacher',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(student_uid, nickname)
);

-- 분석 프레임워크(분류 라벨 세트)
CREATE TABLE analysis_framework (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  labels_json TEXT NOT NULL,   -- 예: ["Pressing","Linking",...,"Directing"]
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 시나리오(대화의 상황)
CREATE TABLE scenario (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  prompt TEXT NOT NULL,            -- 학생 오개념/맥락/문제 설명(내부용)
  student_profile TEXT,            -- 학년/특성 등
  is_active INTEGER NOT NULL DEFAULT 1,
  framework_id INTEGER NOT NULL REFERENCES analysis_framework(id),
  created_by INTEGER REFERENCES user(id),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 세션(교사-학생-튜터 대화)
CREATE TABLE session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id INTEGER NOT NULL REFERENCES scenario(id),
  teacher_id  INTEGER NOT NULL REFERENCES user(id),
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at   DATETIME
);

-- 메시지(3자 대화 로그)
CREATE TABLE message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES session(id),
  role TEXT NOT NULL CHECK(role IN ('student','teacher','tutor')),
  content TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 질문 분석(교사 메시지 단위 태깅)
CREATE TABLE question_analysis (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER NOT NULL REFERENCES message(id),
  label TEXT NOT NULL,           -- 예: Pressing / Linking / ... / Directing
  confidence REAL,               -- 0~1
  meta_json TEXT                 -- 근거/스팬 등
);

-- 세션 요약(빈도/피드백)
CREATE TABLE session_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES session(id),
  distribution_json TEXT NOT NULL, -- {"Pressing":2,"Linking":1,...}
  feedback TEXT,                    -- 강점/개선안
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 3. LLM 설계
### 3.1 모델 분리
- **대화용 LLM**: 학생/튜터 역할 수행, 시나리오와 정책 프롬프트를 엄격히 따른다.
- **분석용 LLM**: 교사 질문(teacher 메시지)만 입력으로 받아 프레임워크 라벨로 분류 + 근거/신뢰도 산출.

### 3.2 프롬프트 자원
- 시나리오별 정책 프롬프트(학생 오개념/문제/아하 조건 등)
- 튜터 정책 프롬프트(개입 조건, 높은/낮은 레버리지 예시, 칭찬/대안 제안 규칙)
- 분석 프롬프트(라벨 정의, 예시, 판정 기준, 출력 JSON 스키마)

## 4. FastAPI 엔드포인트 설계
```
GET  /                -> 홈(시나리오 목록)
GET  /login           -> 로그인 폼(학생ID+닉네임)
POST /login           -> 세션 생성/쿠키 세팅
GET  /scenarios       -> 시나리오 목록(활성화만)
GET  /scenarios/{id}  -> 시나리오 상세/대화 화면
POST /sessions        -> 세션 시작(시나리오ID)
POST /messages        -> 메시지 전송(teacher)
WS   /ws/{session_id} -> 실시간 대화(옵션; 초기버전은 폴링)

-- 관리자
GET  /admin           -> 대시보드
GET  /admin/scenarios -> 목록/검색/필터
POST /admin/scenarios -> 생성
PUT  /admin/scenarios/{id} -> 수정/활성화 토글
GET  /admin/frameworks -> 분석 프레임워크 목록
POST /admin/frameworks -> 등록

-- 내보내기
GET  /sessions/{id}/export.csv  -> CSV 다운로드
```
- 초기 버전은 HTTP 폴링로 구현, 추후 WebSocket 전환.

## 5. 서버 사이드 렌더링(Jinja) 뼈대
- `templates/layout.html`: 헤더/푸터/알림
- `templates/scenarios.html`: 목록 + 활성화 필터
- `templates/chat.html`: 3자 대화 UI, 메시지 스트림, 분석 배지
- `templates/admin/*.html`: 시나리오/프레임워크 CRUD
- `partials/analysis_bar.html`: 빈도 그래프(캔버스) + 요약

## 6. 3자 대화 상태머신
1) **Teacher 입력** ->  
2) **Student LLM 응답** (시나리오 오개념 규칙 준수) ->  
3) **Tutor 감시/개입 판단**  
   - 조건: 대화 정체(최근 N턴 무진전), 주제 이탈, 낮은 레버리지 질문 감지  
   - 개입 시: 대안 질문 제안/칭찬/리프레이즈  
4) **분석 LLM 라벨링** (teacher 메시지에 대해 동기/비동기)  
5) UI 업데이트: 라벨 배지/빈도 카운트/누적 통계

## 7. 분석 파이프라인
- 입력: (teacher_message, framework.labels)
- 출력(JSON):
```json
{
  "label": "Pressing",
  "confidence": 0.84,
  "evidence": "학생이 사용한 표현 X를 근거로...",
  "rationale": "개념적 설명을 유도하는 질문"
}
```
- 세션 종료 시 분포 집계 + 피드백 생성(요약 LLM).

## 8. CSV 스펙
열 순서(예시):
- session_id, scenario_id, scenario_title, student_uid, nickname,
- ts, role, content,
- teacher_label, teacher_confidence,
- summary_feedback

## 9. 보안/개인정보
- 로그인: 학생 고유번호+닉네임만 저장(해시 가능)
- 세션/메시지 데이터 최소 수집
- 관리자 권한 보호(별도 관리자 계정)

## 10. 설정/비밀키
- OPENAI_API_KEY 환경변수
- 모델명: CHAT_MODEL, ANALYSIS_MODEL

## 11. 의존성
- fastapi, uvicorn, jinja2, sqlalchemy, sqlite, httpx, pydantic, python-multipart, (선택)htmx, (선택)passlib

## 12. 예시 정책 프롬프트 요약
- 학생/멘토 말머리, 3학년 분수 오개념, 개입 규칙, ‘아하’ 조건 등 시나리오 프롬프트를 템플릿화하여 시나리오별 변수를 바인딩한다.
