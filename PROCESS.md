# 개발 진행 상황

## Phase 1: 프로젝트 기반 구축 및 데이터 수집

- [x] **로컬 개발 환경 설정**
    - [x] `bitcoin-trading-bot` 디렉터리 생성
    - [x] Python 가상환경 `venv` 생성 및 활성화
    - [x] 필수 라이브러리 (`ccxt`, `pandas`, `supabase-py`, `python-dotenv`) 설치

---

### 다음 단계

- [x] **GitHub 저장소 연결 및 초기 커밋**
    - [x] 로컬 Git 저장소 초기화
    - [x] 원격 GitHub 저장소 연결
    - [x] `.gitignore` 파일 생성 및 설정
    - [x] 핵심 파일들 커밋 및 푸시

- [x] **Supabase 프로젝트 설정**
    - [x] Supabase 웹사이트에서 신규 프로젝트 생성
    - [x] API URL 및 `anon`, `service_role` 키 확보
    - [x] `.gemini` 파일에 Supabase MCP 서버 등록

- [x] **Clerk 통합 (프론트엔드 대시보드)**
    - [x] Next.js 프로젝트 `frontend-dashboard` 생성
    - [x] `@clerk/nextjs` 라이브러리 설치
    - [x] `middleware.ts` 파일 생성 및 설정
    - [x] `app/layout.tsx` 파일 수정
    - [x] Clerk API 키 `.env.local` 파일에 설정
    - [x] Next.js 개발 서버 실행 및 Clerk 통합 확인

- [x] **백엔드 서비스 개발**
    - [x] `backend` 디렉터리 생성
    - [x] `main.py` 파일 생성 및 FastAPI 앱 초기화
    - [x] `requirements.txt` 파일 생성 및 의존성 추가
    - [x] `db.py` 파일 생성 및 Supabase 클라이언트 초기화
    - [x] `/users` API 엔드포인트 추가
