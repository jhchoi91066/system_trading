# 📈 TradingView + BingX 자동매매 시스템

이 프로젝트는 **TradingView Pine Script 신호**를 활용해 **BingX 거래소 API**로 자동 매매를 실행하는 시스템 트레이딩 봇입니다.  
TradingView는 신호(알람)를 보내고, Flask 서버가 이를 받아 BingX API를 통해 주문을 실행합니다.  

TradingView Pine Script → 조건 충족 시 "BUY" or "SELL" 알람 발생

Webhook → TradingView 서버가 내 서버(예: Flask API)로 HTTP POST 전송

내 서버(프로그램) → 알람 메시지 확인 후 BingX API로 주문 실행
---

## 🚀 시스템 아키텍처
TradingView (Pine Script 전략)
│
▼
TradingView Alert
│ (Webhook JSON)
▼
Flask 서버 (/webhook)
│
▼
BingX REST API
│
▼
자동 매수/매도 실행

---

## 📌 구현 단계

### 1. TradingView Pine Script
전략을 차트에 추가합니다.

알람(Alert)을 만들고, Webhook URL을 Flask 서버 주소로 설정합니다.


2. 서버 운영 방법
Flask 서버를 클라우드 VPS (AWS, Vultr, Oracle Free 등) 에 배포

TradingView Alert → VPS 서버 /webhook 으로 신호 전달

VPS는 24시간 작동하므로 PC를 꺼도 자동 매매가 계속 동작

🔒 보안 고려사항
API Key/Secret은 코드에 직접 넣지 말고 환경 변수(.env) 로 관리

Webhook 요청 검증(토큰 또는 서명 확인) 추가 권장

주문 실행 전 로깅 및 에러 핸들링 필수

📈 향후 확장 아이디어
잔고 기반 포지션 크기 동적 계산

손절/익절 로직 추가

여러 종목/타임프레임 지원

Docker 컨테이너화 → 24시간 안정 운영