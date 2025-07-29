# 개발 진행 상황

## Phase 1: 프로젝트 기반 구축 및 데이터 수집 ✅

- [x] **로컬 개발 환경 설정**
- [x] **GitHub 저장소 연결 및 초기 커밋**
- [x] **Supabase 프로젝트 설정**
- [x] **Clerk 통합 (프론트엔드 대시보드)**
- [x] **백엔드 서비스 개발 (FastAPI)**

## Phase 2: 핵심 기능 개발 ✅

- [x] **데이터 수집 및 표시**
    - [x] 거래소, 티커, OHLCV, 심볼 목록 조회 API 구현
- [x] **거래 전략 및 백테스팅**
    - [x] CCI 지표 계산 및 신호 생성 로직 구현
    - [x] 백테스팅 기능 및 API 엔드포인트 구현
- [x] **프론트엔드 UI 개선**
    - [x] 백테스팅을 위한 거래소/심볼 선택 및 파라미터 입력 UI 구현
    - [x] 백테스트 결과 시각화

## Phase 3: Linear 디자인 시스템 적용 ✅

- [x] **Linear 디자인 시스템 통합 및 프론트엔드 리디자인**
- [x] **다국어 지원 (i18n) 기반 마련**

## Phase 4: 실시간 거래 시스템 구축 ✅

- [x] **데이터베이스 스키마 설계**
    - [x] `active_strategies`, `trades`, `portfolio_snapshots`, `strategy_performance` 등 테이블 구조 설계 및 RLS 정책 적용
- [x] **API 키 관리 시스템**
    - [x] 백엔드: API 키 CRUD 엔드포인트 구현 (`/api_keys`)
    - [x] 프론트엔드: API 키 관리 페이지 기능 완성 (조회, 추가, 삭제) 및 로딩/에러 처리
- [x] **실시간 거래 기능**
    - [x] 백엔드: 전략 활성화/비활성화, 수동 거래, 잔고 조회, 거래 내역 추적 API 구현
    - [ ] 프론트엔드: 전략 관리 페이지 기능 완성 필요 (`/strategies`)

## Phase 5: 고급 전략 관리 시스템 ✅

- [x] **사용자 정의 전략 생성 UI/UX**
    - [x] 백엔드: 기본 전략 생성 API 구현 (`/strategies`)
    - [x] 프론트엔드: 다양한 지표(RSI, MACD 등)와 커스텀 스크립트를 지원하는 전략 생성 UI 구현 (동적 파라미터 입력 및 표시)
- [ ] **고급 자금 관리 기능**
    - [x] 백엔드: 전략 활성화 시 관련 파라미터(손절매, 익절, 리스크 등) 수신 기능 구현
    - [ ] 프론트엔드: 자금 관리 및 리스크 설정 UI 구현 필요

## Phase 6: 알림 및 모니터링 시스템 ✅

- [x] **백엔드 알림 및 모니터링 시스템**
    - [x] 알림 생성, 조회, 읽음 처리 등 API 엔드포인트 구현 (`/notifications`)
    - [x] 거래, 리스크, 시스템 알림 생성 로직 구현
    - [x] **WebSocket 구현**: 실시간 모니터링 데이터(포트폴리오, 전략 성과, 알림)를 브로드캐스팅하는 WebSocket 엔드포인트 (`/ws/monitoring`) 구현 완료
    - [x] **Clerk 인증 연동**: WebSocket 연결 시 JWT 토큰 기반 사용자 인증 및 `user_id`별 데이터 브로드캐스트 구현
- [x] **프론트엔드 연동**
    - [x] `WebSocketProvider`를 통해 전역 상태로 실시간 데이터 관리 및 `layout.tsx`에 통합
    - [x] `monitoring/page.tsx`에 실시간 데이터 연동 완료
    - [x] `notifications/page.tsx`에 실시간 데이터 연동 완료
    - [x] 메인 대시보드 (`/page.tsx`)에 실시간 포트폴리오 통계 연동 완료
    - [x] 프론트엔드 `fetch` 요청에 JWT 토큰 포함 (`fetchWithAuth` 구현)
    - [x] `WebSocketProvider`에서 WebSocket 연결 시 초기 메시지로 JWT 토큰 전송

---

## 현재 상태 및 성과

### ✅ 완료된 주요 기능들

1.  **백엔드 핵심 기능**: FastAPI 기반의 백엔드 서버가 구축되었으며, `ccxt`를 통해 여러 거래소의 데이터를 조회하고, CCI 전략을 백테스팅하며, 거래를 실행하는 핵심 기능들이 구현되었습니다.
2.  **데이터베이스 설계**: Supabase(PostgreSQL)를 사용하여 트레이딩 시스템에 필요한 테이블과 RLS 보안 정책이 잘 설계되어 있습니다.
3.  **실시간 데이터 방송 및 인증**: WebSocket을 통해 포트폴리오, 전략 성과, 알림 등 주요 데이터를 실시간으로 전송하며, Clerk JWT를 통한 사용자 인증 및 사용자별 데이터 분리/브로드캐스트가 구현되었습니다.
4.  **프론트엔드 기반 및 실시간 연동**: Next.js, Clerk, `lightweight-charts`를 사용하여 사용자 인증 기반과 미려한 차트 UI를 갖추고 있으며, 주요 페이지(대시보드, 모니터링, 알림)에 실시간 데이터 연동이 완료되었습니다.
5.  **백테스팅 UI**: 사용자가 직접 파라미터를 설정하고 전략을 백테스팅하여 결과를 확인할 수 있는 전체 흐름이 완성되었습니다.
6.  **인증 시스템 통합**: 프론트엔드에서 백엔드 REST API 및 WebSocket 요청 시 Clerk JWT 토큰을 자동으로 포함하도록 구현되었습니다.
7.  **에러 핸들링 및 로딩 상태 개선**: 주요 프론트엔드 페이지에 대한 로딩 및 에러 상태 표시가 개선되었습니다.
8.  **고급 전략 관리 UI**: 전략 생성 시 동적 파라미터 입력 필드 및 전략 목록에 파라미터 표시 기능이 구현되었습니다.

### 🛠 기술 스택

**백엔드**: FastAPI, Python, ccxt, pandas, numpy, Supabase-py, python-jose, WebSocket
**프론트엔드**: Next.js 15, React 19, TypeScript, Tailwind CSS, Clerk Auth, lightweight-charts, i18next
**디자인**: Linear Design System, Glassmorphism
**데이터베이스**: Supabase (PostgreSQL) with Row Level Security

### 🚀 다음 단계 고려사항

1.  **프론트엔드 페이지 기능 완성**:
    *   `/strategies` 페이지의 UI를 백엔드 API와 연동하여 실제 기능(생성, 활성화, 비활성화)을 완성해야 합니다.
2.  **고급 자금 관리 기능 구현**: 프론트엔드에 자금 관리 및 리스크 설정 UI를 구현합니다.
3.  **추가 기능 구현**: 거래 내역, 백테스팅 시각화, 사용자 설정 등 추가 기능을 고려합니다.

### 🎯 프로젝트 완성도: 약 85%

핵심 백엔드 로직과 프론트엔드 UI 기반은 잘 갖춰져 있으며, 실시간 데이터 연동 및 인증 시스템 통합이 완료되었습니다. 이제 사용자 인터페이스의 나머지 부분을 완성하고 고급 기능을 추가하는 단계입니다.

---

## ⚠️ 현재 해결해야 할 문제

1.  **Supabase API 키 문제**: 백엔드에서 Supabase와 통신 시 `Invalid API key` 오류가 발생하여 `/strategies` 엔드포인트 등 Supabase를 사용하는 기능들이 `500 Internal Server Error`를 반환하고 있습니다. `.env` 파일의 `SUPABASE_KEY`를 Supabase 프로젝트 대시보드에서 복사한 올바른 `anon public` 키로 업데이트해야 합니다.
2.  **WebSocket `control frame too long` 오류**: `uvicorn` 실행 시 `max_size` 옵션을 설정했음에도 불구하고 WebSocket 연결 시 `control frame too long` 오류가 계속 발생하고 있습니다. 이는 WebSocket 초기 인증 메시지의 크기가 너무 크거나, `uvicorn`의 `websockets` 백엔드 처리 방식에 문제가 있을 수 있습니다. 추가적인 조사가 필요합니다.

