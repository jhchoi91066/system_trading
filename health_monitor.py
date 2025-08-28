#!/usr/bin/env python3
"""
Bitcoin Trading Bot - Health Monitor
지속적으로 시스템 상태를 모니터링하고 문제 발생 시 자동 복구를 시도합니다.
"""

import asyncio
import aiohttp
import time
import subprocess
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./logs/health-monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.webhook_url = "http://localhost:8081"
        self.check_interval = 30  # 30초마다 체크
        self.failed_checks = {}
        self.max_failures = 3  # 3회 실패 시 자동 복구 시도
        self.last_notification = {}
        
    async def check_backend_health(self) -> Dict:
        """백엔드 서비스 헬스체크"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"{self.backend_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "service": "backend",
                            "status": "healthy",
                            "details": data
                        }
                    else:
                        return {
                            "service": "backend",
                            "status": "unhealthy",
                            "error": f"HTTP {response.status}"
                        }
        except Exception as e:
            return {
                "service": "backend",
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_webhook_health(self) -> Dict:
        """웹훅 서비스 헬스체크"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # 웹훅 서버의 간단한 연결 테스트
                async with session.get(f"{self.webhook_url}/health") as response:
                    if response.status == 200:
                        return {
                            "service": "webhook",
                            "status": "healthy"
                        }
                    else:
                        return {
                            "service": "webhook", 
                            "status": "unhealthy",
                            "error": f"HTTP {response.status}"
                        }
        except Exception as e:
            # 웹훅 서버에 /health 엔드포인트가 없을 수 있으므로 포트 연결만 확인
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get(f"{self.webhook_url}") as response:
                        return {
                            "service": "webhook",
                            "status": "healthy" if response.status in [200, 404, 405] else "unhealthy"
                        }
            except:
                return {
                    "service": "webhook",
                    "status": "unhealthy", 
                    "error": str(e)
                }
    
    def check_pm2_status(self) -> Dict:
        """PM2 프로세스 상태 확인"""
        try:
            result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True)
            if result.returncode == 0:
                processes = json.loads(result.stdout)
                status = {}
                for proc in processes:
                    status[proc['name']] = {
                        'pid': proc['pid'],
                        'status': proc['pm2_env']['status'],
                        'restart_time': proc['pm2_env']['restart_time'],
                        'unstable_restarts': proc['pm2_env']['unstable_restarts']
                    }
                return {
                    "service": "pm2",
                    "status": "healthy",
                    "processes": status
                }
            else:
                return {
                    "service": "pm2",
                    "status": "unhealthy",
                    "error": result.stderr
                }
        except Exception as e:
            return {
                "service": "pm2", 
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def auto_recovery(self, service: str, error_info: Dict):
        """자동 복구 시도"""
        logger.warning(f"🔄 Attempting auto-recovery for {service}")
        
        if service == "backend":
            try:
                subprocess.run(['pm2', 'restart', 'trading-backend'], check=True)
                logger.info(f"✅ Successfully restarted {service}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to restart {service}: {e}")
                return False
                
        elif service == "webhook":
            try:
                subprocess.run(['pm2', 'restart', 'tradingview-webhook'], check=True)
                logger.info(f"✅ Successfully restarted {service}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to restart {service}: {e}")
                return False
        
        return False
    
    async def run_health_checks(self) -> List[Dict]:
        """모든 헬스체크 실행"""
        checks = await asyncio.gather(
            self.check_backend_health(),
            self.check_webhook_health(),
            return_exceptions=True
        )
        
        # PM2 상태도 추가
        pm2_status = self.check_pm2_status()
        checks.append(pm2_status)
        
        return checks
    
    async def process_check_results(self, results: List[Dict]):
        """헬스체크 결과 처리"""
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check exception: {result}")
                continue
                
            service = result['service']
            status = result['status']
            
            if status == "unhealthy":
                # 실패 카운트 증가
                self.failed_checks[service] = self.failed_checks.get(service, 0) + 1
                logger.warning(f"🚨 {service} is unhealthy (failures: {self.failed_checks[service]}/{self.max_failures})")
                
                # 최대 실패 횟수 도달 시 자동 복구 시도
                if self.failed_checks[service] >= self.max_failures:
                    await self.auto_recovery(service, result)
                    self.failed_checks[service] = 0  # 복구 시도 후 카운터 리셋
                    
            else:
                # 성공 시 실패 카운터 리셋
                if service in self.failed_checks:
                    logger.info(f"✅ {service} recovered")
                    del self.failed_checks[service]
    
    async def monitor_loop(self):
        """메인 모니터링 루프"""
        logger.info("🔍 Health Monitor started")
        
        while True:
            try:
                logger.info("Running health checks...")
                results = await self.run_health_checks()
                await self.process_check_results(results)
                
                # 건강한 서비스들 요약
                healthy_services = [r['service'] for r in results if r.get('status') == 'healthy']
                if healthy_services:
                    logger.info(f"✅ Healthy services: {', '.join(healthy_services)}")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Monitor loop error: {e}")
                await asyncio.sleep(5)

async def main():
    monitor = HealthMonitor()
    await monitor.monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())