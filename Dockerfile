# 백엔드용 Python Dockerfile
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node.js 18 설치 (PM2용)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# PM2 글로벌 설치
RUN npm install -g pm2

# Python 의존성 파일 복사
COPY backend/requirements.txt .

# Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 코드 복사
COPY backend/ .

# 환경 변수 파일 복사
COPY .env .

# PM2 ecosystem 파일 복사
COPY ecosystem.config.js .

# 포트 노출
EXPOSE 8000

# PM2로 애플리케이션 시작
CMD ["pm2-runtime", "start", "ecosystem.config.js"]