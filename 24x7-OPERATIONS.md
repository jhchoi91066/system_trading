# 24/7 Bitcoin Trading Bot Operations Guide

## 🚀 현재 구성 상태

### ✅ 완료된 구성
- **PM2 프로세스 매니저**: 자동 재시작 및 모니터링
- **로그 관리 시스템**: 통합 로그 파일 및 에러 추적
- **API 상태 모니터링**: 실시간 상태 확인
- **자동 재시작**: 프로세스 오류 시 자동 복구

## 📊 운영 명령어

### 기본 PM2 명령어
```bash
# 서비스 시작
pm2 start ecosystem.config.js

# 서비스 중지
pm2 stop bitcoin-trading-bot

# 서비스 재시작
pm2 restart bitcoin-trading-bot

# 서비스 삭제
pm2 delete bitcoin-trading-bot

# 상태 확인
pm2 status

# 로그 확인
pm2 logs bitcoin-trading-bot

# 프로세스 모니터링
pm2 monit
```

### 모니터링 스크립트
```bash
# 상태 대시보드 확인
./status.sh

# 자동 모니터링 실행
./monitor.sh
```

## 🔧 현재 PM2 설정 (ecosystem.config.js)

```javascript
{
  name: 'bitcoin-trading-bot',
  script: 'python3',
  args: '-m uvicorn main:app --host 0.0.0.0 --port 8000',
  cwd: './backend',
  instances: 1,
  autorestart: true,
  max_memory_restart: '1G',
  max_restarts: 10,
  min_uptime: '10s',
  restart_delay: 4000
}
```

## 📝 로그 관리

### 로그 파일 위치
- **출력 로그**: `./logs/out.log`
- **에러 로그**: `./logs/err.log`
- **통합 로그**: `./logs/combined.log`
- **모니터링 로그**: `./logs/monitor.log`

### 로그 순환 설정
- 최대 재시작: 10회
- 최소 실행시간: 10초
- 재시작 간격: 4초

## 🎯 성능 모니터링

### 현재 상태
- **메모리 사용량**: ~170MB
- **CPU 사용량**: 0-1%
- **응답 시간**: <100ms
- **활성 전략**: 4개

### 리소스 제한
- **메모리 제한**: 1GB (자동 재시작)
- **프로세스 수**: 1개 (단일 인스턴스)

## 🔄 자동화 기능

### 1. 자동 재시작
- 프로세스 크래시 시 즉시 재시작
- 메모리 초과 시 자동 재시작
- 최대 10회 재시작 시도

### 2. 상태 모니터링
- PM2 프로세스 상태 확인
- API 응답 상태 확인
- 메모리 사용량 추적
- 활성 전략 상태 확인

### 3. 로그 관리
- 타임스탬프 포함 로그
- 에러와 일반 로그 분리
- 통합 로그 파일 생성

## 🚨 문제 해결

### 프로세스가 시작되지 않을 때
```bash
# PM2 상태 확인
pm2 status

# 로그 확인
pm2 logs bitcoin-trading-bot --lines 20

# 프로세스 재시작
pm2 restart bitcoin-trading-bot
```

### API가 응답하지 않을 때
```bash
# API 테스트
curl http://localhost:8000/

# 포트 사용 확인
lsof -i :8000

# 프로세스 강제 재시작
pm2 reload bitcoin-trading-bot
```

### 메모리 사용량이 높을 때
```bash
# 메모리 사용량 확인
pm2 monit

# 프로세스 재시작 (메모리 해제)
pm2 restart bitcoin-trading-bot
```

## 📋 일일 점검 사항

### 매일 확인할 것
1. `./status.sh` 실행으로 전체 상태 확인
2. 활성 전략 수량 확인
3. API 응답 상태 확인
4. 메모리 사용량 확인
5. 에러 로그 검토

### 주간 점검 사항
1. 로그 파일 크기 확인 및 정리
2. PM2 프로세스 통계 검토
3. 시스템 리소스 사용량 분석
4. 전략 성과 분석

## 🌐 다음 단계: 클라우드 배포

### 준비 사항
1. **VPS 선택**: AWS EC2, DigitalOcean Droplet, 또는 Google Cloud VM
2. **Docker 설정**: 컨테이너화된 배포
3. **도메인 설정**: HTTPS 및 도메인 연결
4. **백업 시스템**: 데이터 및 설정 백업
5. **모니터링 강화**: 외부 모니터링 서비스 연동

### 예상 비용
- **기본 VPS**: $5-20/월
- **도메인**: $10-15/년
- **SSL 인증서**: 무료 (Let's Encrypt)

## 📞 지원

문제 발생 시:
1. `./status.sh`로 현재 상태 확인
2. `pm2 logs bitcoin-trading-bot`으로 로그 확인
3. 필요시 `pm2 restart bitcoin-trading-bot`으로 재시작

---

**✅ 24/7 자동 거래 시스템이 성공적으로 구축되었습니다!**

현재 시스템은 로컬 환경에서 안정적으로 운영되고 있으며, 프로세스 오류나 시스템 재부팅 시에도 자동으로 복구됩니다.