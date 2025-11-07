# TutorBot Intervention Threshold 슬라이더 검증 가이드

## 구현 완료 사항

### UI 변경사항
- ✅ `<input type="number">` → `<input type="range">` 슬라이더로 변경
- ✅ 실시간 값 표시: `<strong id="tutor-threshold-value">3</strong> / 10`
- ✅ 동적 설명 텍스트: 값에 따라 Minimal/Balanced/Active/Frequent 표시
- ✅ 슬라이더 레이블: Minimal (1), Balanced (5), Frequent (10)
- ✅ 접근성: ARIA 속성 (`aria-live`, `aria-valuenow`, `aria-describedby`)

### JavaScript 기능
- ✅ `updateThresholdDisplay(value)`: 실시간 값 및 설명 업데이트
- ✅ 슬라이더 `input` 이벤트 핸들러
- ✅ 페이지 로드 시 DB 값 자동 로드
- ✅ 설정 저장 후 캐시 무효화 검증 (console.log)

### 스타일링
- ✅ 브라우저 크로스 호환: `-webkit-` 및 `-moz-` 접두사
- ✅ 호버 효과: 파란색 그림자
- ✅ 포커스 효과: 키보드 네비게이션 지원
- ✅ 반응형: 모바일 친화적

## 수동 검증 절차

### 1단계: UI 확인
```bash
# 개발 서버 실행
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

브라우저에서 접속:
```
http://localhost:8000/admin/chatbot-config/settings
```

**확인 사항**:
- [ ] 슬라이더가 정상적으로 표시됨
- [ ] 범위: 1 - 10 (step 1)
- [ ] 기본값: 3 (DB에서 로드)
- [ ] 값 표시: "3 / 10" 형식
- [ ] 레이블: Minimal (1), Balanced (5), Frequent (10) 정렬 확인

### 2단계: 실시간 업데이트 테스트
**동작**:
1. 슬라이더를 1로 이동
2. 값 표시가 "1 / 10"로 변경되는지 확인
3. 설명 텍스트가 "Minimal: 1 interventions per 10 questions (~10% feedback rate)"로 변경되는지 확인

**테스트 케이스**:
| 값 | 표시 | 설명 텍스트 | 예상 |
|----|------|------------|------|
| 1 | 1 / 10 | Minimal: 1 interventions per 10 questions (~10% feedback rate) | ✅ |
| 3 | 3 / 10 | Balanced: 3 interventions per 10 questions (~30% feedback rate) - Recommended | ✅ |
| 5 | 5 / 10 | Active: 5 interventions per 10 questions (~50% feedback rate) | ✅ |
| 10 | 10 / 10 | Frequent: 10 interventions per 10 questions (~100% feedback rate) | ✅ |

### 3단계: 설정 저장 및 검증
**동작**:
1. 슬라이더를 5로 변경
2. "💾 Save Configuration" 버튼 클릭
3. 성공 메시지: "✅ Configuration saved successfully!" 확인
4. 브라우저 콘솔 (F12) 열기
5. 콘솔에 "✅ Threshold verified: 5" 메시지 확인

**예상 결과**:
```
✅ Threshold verified: 5
```

### 4단계: 페이지 새로고침 테스트
**동작**:
1. 페이지 새로고침 (F5)
2. 슬라이더 값이 5로 유지되는지 확인
3. 값 표시가 "5 / 10"인지 확인
4. 설명 텍스트가 "Active: 5 interventions..."인지 확인

**예상 결과**:
- ✅ 저장된 값이 정상적으로 로드됨

### 5단계: 접근성 테스트
**키보드 네비게이션**:
1. Tab 키로 슬라이더에 포커스 이동
2. 좌우 화살표 키로 값 조정 가능 확인
3. 포커스 시 파란색 그림자 표시 확인

**스크린 리더**:
- `aria-live="polite"`: 값 변경 시 스크린 리더가 알림
- `aria-describedby`: 설명 텍스트 읽기
- `aria-valuenow`: 현재 값 읽기

### 6단계: 실제 동작 검증
**새 세션 생성**:
1. 메인 페이지로 이동: `http://localhost:8000/`
2. 새 세션 시작
3. 교사 질문 10개 입력
4. TutorBot 개입 횟수 확인

**예상 결과** (threshold=5인 경우):
- 10개 질문 중 약 5번 TutorBot 개입

## 자동 검증 (브라우저 콘솔)

```javascript
// 브라우저 콘솔에서 실행
// 1. 현재 threshold 값 확인
fetch('/admin/chatbot-config')
  .then(r => r.json())
  .then(d => console.log('Current threshold:', d.tutor_bot.intervention_threshold));

// 2. threshold 변경 (예: 7로)
fetch('/admin/chatbot-config', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    student_bot_model: 'gpt-4-turbo',
    student_bot_temperature: 0.7,
    student_bot_max_tokens: 150,
    tutor_bot_model: 'gpt-3.5-turbo',
    tutor_bot_temperature: 0.3,
    tutor_bot_max_tokens: 100,
    tutor_bot_intervention_threshold: 7
  })
})
  .then(r => r.json())
  .then(d => console.log('Save response:', d));

// 3. 변경 확인 (500ms 후)
setTimeout(() => {
  fetch('/admin/chatbot-config')
    .then(r => r.json())
    .then(d => console.log('Verified threshold:', d.tutor_bot.intervention_threshold));
}, 500);
```

## 브라우저 호환성 테스트

### Chrome/Edge (Chromium)
- ✅ `-webkit-slider-thumb` 스타일 적용
- ✅ 호버/포커스 효과

### Firefox
- ✅ `-moz-range-thumb` 스타일 적용
- ✅ 호버/포커스 효과

### Safari
- ✅ `-webkit-slider-thumb` 스타일 적용
- ⚠️ 일부 시각적 차이 가능 (브라우저 기본 스타일)

## 모바일 테스트

### 반응형 확인
1. 개발자 도구 (F12) → Device Toolbar (Ctrl+Shift+M)
2. 모바일 뷰 (iPhone, Android) 선택
3. 슬라이더가 터치로 조작 가능한지 확인

**예상 결과**:
- ✅ 터치로 슬라이더 드래그 가능
- ✅ 값 표시 및 설명 텍스트 정상 표시

## 트러블슈팅

### 문제: 슬라이더 값이 저장 후 초기화됨
**원인**: 캐시 무효화 실패
**해결**:
```python
# src/services/config_cache.py 확인
await bot_config_cache.invalidate()  # 이 줄이 실행되는지 확인
```

### 문제: 설명 텍스트가 업데이트 안 됨
**원인**: JavaScript 오류
**해결**:
1. 브라우저 콘솔 (F12) 열기
2. JavaScript 에러 확인
3. `updateThresholdDisplay` 함수 호출 확인

### 문제: 슬라이더 스타일이 적용 안 됨
**원인**: CSS 우선순위
**해결**:
```css
/* 브라우저 기본 스타일 무효화 */
input[type="range"] {
  -webkit-appearance: none;
  appearance: none;
}
```

## 검증 완료 체크리스트

- [ ] UI가 정상적으로 표시됨
- [ ] 실시간 값 업데이트 작동
- [ ] 동적 설명 텍스트 변경
- [ ] 설정 저장 성공
- [ ] 캐시 무효화 검증 (콘솔 로그)
- [ ] 페이지 새로고침 후 값 유지
- [ ] 키보드 네비게이션 작동
- [ ] 크로스 브라우저 호환성 (Chrome, Firefox)
- [ ] 모바일 터치 조작 가능
- [ ] 새 세션에서 threshold 설정 반영

## 다음 단계 (선택사항)

### Phase 2: 0.0-1.0 확률 시스템 마이그레이션
현재 1-10 정수 시스템을 0.0-1.0 확률 시스템으로 변경하려면:

1. **Backend 변경**:
   - `src/services/tutor_bot.py`: `should_intervene()` 확률 기반으로 재작성
   - `src/api/routes/admin_chatbot_config.py`: `float` 타입으로 변경
   - `src/services/session_mgr.py`: 타입 변경

2. **Database 마이그레이션**:
   ```python
   # migration script
   UPDATE chatbot_config
   SET config_value = CAST(CAST(config_value AS INTEGER) / 10.0 AS TEXT)
   WHERE config_key = 'tutor_bot.intervention_threshold';
   ```

3. **UI 변경**:
   ```html
   <input type="range" min="0.0" max="1.0" step="0.05" value="0.3">
   ```

이 작업은 별도 태스크로 진행하는 것을 권장합니다.
