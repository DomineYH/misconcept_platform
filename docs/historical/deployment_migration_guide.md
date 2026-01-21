# 챗봇 설정 마이그레이션 가이드

## 배경

**버전 0.8.8 이후**부터 챗봇 설정 관리가 데이터베이스 기반에서 `.env` 파일 기반으로 변경되었습니다.

### 변경 이유
- 챗봇 설정은 실시간으로 자주 변경되는 값이 아님
- `.env`로 관리하는 것이 더 단순하고 Git을 통한 버전 관리도 용이
- 코드 복잡도 감소 (약 1,500줄 제거)
- 설정 로드 속도 100배 개선 (~10ms → ~0.1ms)

## Breaking Changes

### 제거된 기능
1. **관리자 UI**: `/admin/chatbot-config/*` 엔드포인트 완전 제거
2. **데이터베이스 테이블**: `chatbot_config`, `chatbot_config_audit` 삭제
3. **API 엔드포인트**:
   - `GET /admin/chatbot-config/settings`
   - `GET /admin/chatbot-config/`
   - `PUT /admin/chatbot-config/`
   - `POST /admin/chatbot-config/reset`
   - `GET /admin/chatbot-config/costs`

### 새로운 설정 방법
모든 챗봇 설정은 `.env` 파일을 통해 관리됩니다.

## 마이그레이션 절차

### 1. 기존 설정값 백업
```bash
# 데이터베이스에서 현재 설정 확인
sqlite3 dialogue_sim.db "SELECT config_key, config_value FROM chatbot_config;" > current_config.txt

# 전체 데이터베이스 백업
sqlite3 dialogue_sim.db ".dump chatbot_config" > backup_chatbot_config.sql
sqlite3 dialogue_sim.db ".dump chatbot_config_audit" > backup_chatbot_config_audit.sql
```

### 2. .env 파일 업데이트
기존 데이터베이스의 설정값을 `.env` 파일에 추가합니다.

```bash
# StudentBot 설정
STUDENT_TEMPERATURE=0.7        # 0.0-2.0 (높을수록 창의적)
STUDENT_MAX_TOKENS=150         # 최대 응답 길이

# TutorBot 설정
TUTOR_TEMPERATURE=0.3          # 0.0-2.0 (일관적인 피드백)
TUTOR_MAX_TOKENS=100           # 최대 피드백 길이
TUTOR_INTERVENTION_THRESHOLD=3 # 질문 10개당 개입 횟수 (1-10)
```

### 3. 데이터베이스 마이그레이션 실행
```bash
# 마이그레이션 스크립트 실행
sqlite3 dialogue_sim.db < src/db/migrations/003_remove_chatbot_config.sql

# 결과 확인
sqlite3 dialogue_sim.db ".tables" | grep -v chatbot_config
# chatbot_config, chatbot_config_audit가 목록에 없어야 함
```

### 4. 코드 업데이트
```bash
# 최신 코드 pull
git pull origin main  # 또는 해당 브랜치

# 의존성 업데이트
uv pip install -e ".[dev]"
```

### 5. 서버 재시작
```bash
# systemd 사용 시
sudo systemctl restart misconcept_platform

# 또는 직접 실행 시
pkill uvicorn
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 검증
```bash
# Health check
curl http://localhost:8000/health

# 설정 확인
python -c "from src.config import config; print('STUDENT_TEMPERATURE:', config.STUDENT_TEMPERATURE); print('TUTOR_TEMPERATURE:', config.TUTOR_TEMPERATURE)"

# 테스트 실행
pytest tests/integration/test_full_dialogue_flow.py -v
```

## 설정 변경 방법 (마이그레이션 후)

### 프로덕션 환경
1. `.env` 파일 수정
2. 서버 재시작: `systemctl restart misconcept_platform`
3. Health check로 확인

### Docker 환경
```bash
# docker-compose.yml에서 환경 변수 수정
environment:
  - STUDENT_TEMPERATURE=0.8
  - TUTOR_TEMPERATURE=0.3
  # ...

# 컨테이너 재시작
docker-compose restart
```

### 개발 환경
```bash
# .env 파일 수정
vi .env

# 서버 재시작 (--reload 옵션 사용 시 자동 재시작됨)
# 또는 수동 재시작
uvicorn src.main:app --reload
```

## 시나리오별 설정 (선택 사항)

시나리오별로 다른 챗봇 설정을 사용하려면 데이터베이스에서 직접 수정할 수 있습니다.

```sql
-- 특정 시나리오에 대해 temperature 오버라이드
UPDATE scenario
SET chat_temperature = 0.9, tutor_intervention_threshold = 5
WHERE id = 1;

-- 오버라이드 제거 (글로벌 설정 사용)
UPDATE scenario
SET chat_temperature = NULL, tutor_intervention_threshold = NULL
WHERE id = 1;
```

**우선순위**:
1. 시나리오별 오버라이드 (scenario 테이블)
2. 환경 변수 (.env)
3. 하드코딩된 기본값

## 롤백 절차

문제 발생 시 이전 버전으로 롤백할 수 있습니다.

### 1. 코드 롤백
```bash
# 이전 커밋으로 되돌리기
git revert <commit-hash>

# 또는 특정 버전으로 체크아웃
git checkout v0.8.8
```

### 2. 데이터베이스 복원
```bash
# 백업에서 테이블 복원
sqlite3 dialogue_sim.db < backup_chatbot_config.sql
sqlite3 dialogue_sim.db < backup_chatbot_config_audit.sql
```

### 3. 의존성 재설치
```bash
uv pip install -e ".[dev]"
```

### 4. 서버 재시작
```bash
systemctl restart misconcept_platform
```

## FAQ

### Q1: 왜 관리자 UI를 제거했나요?
**A**: 챗봇 설정은 실시간으로 자주 변경되는 값이 아니며, `.env`로 관리하는 것이 더 단순하고 Git을 통한 버전 관리도 용이합니다. 코드 복잡도를 줄이고 유지보수를 쉽게 하기 위한 결정입니다.

### Q2: 시나리오별 설정은 어떻게 하나요?
**A**: 시나리오 생성 시 또는 직접 DB 수정으로 설정 가능합니다. 시나리오 테이블의 `chat_temperature`, `tutor_intervention_threshold` 컬럼을 수정하면 해당 시나리오에만 적용됩니다.

### Q3: 설정 변경 이력은 어떻게 추적하나요?
**A**: `.env` 파일을 Git으로 관리하면 변경 이력 추적이 가능합니다. 다만, `.env`는 보안상 `.gitignore`에 포함되므로, 설정 템플릿(`.env.example`)만 버전 관리하는 것이 일반적입니다.

### Q4: 프로덕션 환경에서 설정을 바꾸려면?
**A**:
1. `.env` 파일 수정
2. 서버 재시작 (`systemctl restart misconcept_platform`)
3. Health check로 정상 동작 확인

Docker 환경이라면 환경 변수를 컨테이너 재시작 시 주입하면 됩니다.

### Q5: 캐시 성능 최적화가 사라지는데 괜찮나요?
**A**: 환경 변수 조회는 캐시 조회보다 훨씬 빠릅니다 (~0.1ms vs ~10ms). 오히려 성능이 개선됩니다.

### Q6: 기존 시나리오별 설정 데이터는 어떻게 되나요?
**A**: 마이그레이션 스크립트는 `scenario` 테이블의 챗봇 설정 컬럼을 제거하지 않습니다. 시나리오별 오버라이드는 계속 사용 가능합니다. 단, `chatbot_config` 테이블에 저장된 글로벌 설정은 삭제되므로 마이그레이션 전에 백업하세요.

### Q7: 마이그레이션 스크립트를 실행하지 않으면 어떻게 되나요?
**A**: 서버는 정상적으로 시작되지만, `chatbot_config` 테이블이 여전히 존재하므로 불필요한 공간을 차지합니다. 또한 코드가 해당 테이블을 참조하지 않으므로 정리하는 것을 권장합니다.

## 참고 자료

- **변경 사항 상세**: `CHANGELOG.md`
- **새로운 설정 방법**: `README.md` - Chatbot Configuration 섹션
- **마이그레이션 스크립트**: `src/db/migrations/003_remove_chatbot_config.sql`

## 지원

문제가 발생하면 다음을 확인하세요:
1. `.env` 파일에 모든 필수 환경 변수가 설정되어 있는지 확인
2. 서버 로그에서 에러 메시지 확인
3. Health check 엔드포인트로 서버 상태 확인
4. 필요 시 롤백 절차에 따라 이전 버전으로 복원

---

**Version**: 0.8.9+ | **Last Updated**: 2025-11-17
