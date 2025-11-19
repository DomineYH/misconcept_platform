# 대화 오류 디버깅 가이드

대화 시작 후 학생/튜터 봇의 응답이 표시되지 않는 문제 디버깅 가이드입니다.

## 🔍 빠른 진단 체크리스트

### 1. 브라우저 개발자 도구 열기
- **Chrome/Edge**: F12 또는 우클릭 → 검사
- **Firefox**: F12 또는 우클릭 → 요소 검사
- **Safari**: Cmd+Option+I

### 2. Console 탭 확인
대화 페이지를 열면 다음 메시지들이 표시되어야 합니다:
```
💬 Chat initialized. Session ID: 123
📋 To enable HTMX debug logging, run in console: htmx.config.debugLoggingEnabled = true
```

### 3. HTMX 디버그 모드 활성화
Console에 다음을 입력:
```javascript
htmx.config.debugLoggingEnabled = true
```

이제 모든 HTMX 요청/응답이 Console에 표시됩니다.

## 🐛 일반적인 오류 패턴

### 문제 1: 메시지를 보내도 아무 응답이 없음

**증상**:
- "전송" 버튼 클릭 시 "응답 생성 중..." 표시
- 몇 초 후 아무 변화 없음
- Console에 오류 메시지

**진단 단계**:

1. **Network 탭 확인**
   - POST `/sessions/{id}/messages` 요청 찾기
   - Status 확인:
     - `200 OK` → Response 탭에서 HTML 확인
     - `500` → 서버 오류 (터미널 로그 확인)
     - `400` → 요청 데이터 오류

2. **Console 오류 확인**
   ```
   ❌ No valid message IDs found! All IDs are NaN or null
   ```
   → 메시지 HTML이 `data-message-id` 속성을 포함하지 않음

3. **서버 로그 확인**
   터미널에서 다음 로그 찾기:
   ```
   ERROR: Message missing 'id' attribute
   ERROR: Rendered HTML invalid or empty for message
   ERROR: No messages rendered for session
   ```

### 문제 2: Message ID가 NaN으로 표시됨

**증상**:
Console에 다음 메시지:
```
⚠️ Invalid message ID found: undefined
❌ No valid message IDs found! All IDs are NaN or null
```

**원인**:
- 메시지 partial 템플릿이 `data-message-id` 속성을 설정하지 않음
- 메시지 객체에 `id` 속성이 없음

**해결 방법**:
1. `src/templates/partials/message.html` 확인:
   ```html
   <div class="message" data-message-id="{{ message.id }}">
   ```

2. 서버 로그에서 메시지 생성 오류 확인:
   ```
   logger.error(f"Message missing 'id' attribute")
   ```

### 문제 3: API 응답은 200 OK인데 빈 HTML

**증상**:
- Network 탭에서 Status: `200 OK`
- Response 탭이 비어 있거나 `<div>` 태그만 있음
- Console에 메시지 표시 안 됨

**원인**:
- SessionManager가 메시지를 생성했지만 DB flush가 즉시 일어나지 않음
- `new_messages` 쿼리가 빈 결과를 반환

**해결 방법**:
1. 서버 로그 확인:
   ```
   INFO: Rendered 0/3 messages for session 123
   ERROR: No messages rendered for session 123. Total messages attempted: 3
   ```

2. 데이터베이스 확인:
   ```bash
   sqlite3 dialogue_sim.db "SELECT id, role, content FROM message ORDER BY id DESC LIMIT 5;"
   ```

### 문제 4: 500 Internal Server Error

**증상**:
- Network 탭에서 Status: `500`
- Response에 JSON 에러 메시지

**진단**:
1. **터미널 로그 확인**:
   ```
   ERROR: Failed to render message: ...
   ERROR: No messages rendered for session 123
   ```

2. **Stack trace 분석**:
   - Template rendering error → `partials/message.html` 확인
   - Database error → DB 연결 및 스키마 확인
   - OpenAI API error → API 키 및 모델 설정 확인

## 📊 정상 작동 시 Console 로그

메시지를 성공적으로 보내면 다음과 같은 로그가 표시됩니다:

```
📨 New messages added via HTMX swap
📊 Total messages in DOM: 3
  Message 0: ID=1, role=teacher, content="안녕하세요..."
  Message 1: ID=2, role=student, content="네, 안녕하세요..."
  Message 2: ID=3, role=tutor, content="잘하고 있어요..."
📊 Found 3 valid message IDs. Max: 3
✅ Updated last_message_id to: 3
📜 Scrolled to bottom
```

## 🔧 서버 측 디버깅

### 1. 로깅 레벨 확인
`.env` 파일:
```bash
LOG_LEVEL=DEBUG  # 상세 로그 활성화
```

### 2. 메시지 렌더링 로그 확인
터미널에서 다음 로그 찾기:
```
INFO: Rendered 3/3 messages for session 123
DEBUG: Successfully rendered message 2 (student)
```

### 3. 데이터베이스 직접 확인
```bash
# 최근 메시지 확인
sqlite3 dialogue_sim.db "SELECT * FROM message ORDER BY created_at DESC LIMIT 10;"

# 특정 세션의 메시지
sqlite3 dialogue_sim.db "SELECT id, role, substring(content, 1, 50) FROM message WHERE session_id=123;"
```

## 🚀 테스트 절차

### 1. 서버 실행
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 브라우저에서 테스트
1. http://localhost:8000/scenarios 접속
2. 시나리오 선택
3. F12로 개발자 도구 열기
4. Console 탭에서 `htmx.config.debugLoggingEnabled = true` 실행
5. 메시지 전송 테스트

### 3. 정상 동작 확인
- ✅ "전송" 버튼 클릭 후 "응답 생성 중..." 표시
- ✅ 1-3초 후 학생 봇 응답 표시
- ✅ (조건 충족 시) 튜터 피드백 표시
- ✅ Console에 📨, ✅ 메시지 표시
- ✅ Network 탭에서 200 OK 응답 확인

## 📝 추가 리소스

### 관련 파일
- **프론트엔드**: `src/templates/chat.html:72-249` (JavaScript 로직)
- **백엔드**: `src/api/routes/sessions.py:102-174` (메시지 렌더링)
- **템플릿**: `src/templates/partials/message.html` (메시지 HTML)
- **서비스**: `src/services/session_mgr.py` (메시지 생성 로직)

### 로그 위치
- **서버 로그**: 터미널 출력 (uvicorn)
- **브라우저 로그**: 개발자 도구 Console 탭
- **데이터베이스**: `dialogue_sim.db`

### 도움말
문제가 계속되면 다음 정보와 함께 이슈 보고:
1. 브라우저 Console 전체 로그 (Screenshot)
2. Network 탭의 POST 요청 상세 (Headers + Response)
3. 서버 터미널 로그 (에러 부분)
4. 데이터베이스 메시지 테이블 상태
