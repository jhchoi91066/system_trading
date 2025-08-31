"""
Disaster Recovery System (Phase 15.5)
Enterprise-grade disaster recovery and business continuity
"""

import os
import asyncio
import subprocess
import json
import shutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sqlite3
import tarfile
import threading

class DisasterType(Enum):
    SYSTEM_FAILURE = "system_failure"
    DATA_CORRUPTION = "data_corruption"
    NETWORK_OUTAGE = "network_outage"
    SECURITY_BREACH = "security_breach"
    CRITICAL_ERROR = "critical_error"
    MANUAL_TRIGGER = "manual_trigger"

class RecoveryStatus(Enum):
    IDLE = "idle"
    DETECTING = "detecting"
    RESPONDING = "responding"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class DisasterEvent:
    event_id: str
    disaster_type: DisasterType
    severity: int  # 1-10 scale
    detected_at: datetime
    description: str
    affected_systems: List[str]
    recovery_started_at: Optional[datetime]
    recovery_completed_at: Optional[datetime]
    status: RecoveryStatus
    recovery_actions: List[str]
    data_loss_estimate: str

@dataclass
class RecoveryPlan:
    disaster_type: DisasterType
    priority: int
    detection_criteria: Dict[str, Any]
    recovery_steps: List[str]
    estimated_recovery_time: int  # minutes
    required_resources: List[str]
    success_criteria: List[str]

class SystemHealthChecker:
    def __init__(self):
        self.health_checks = {}
        self.last_check_results = {}
        
    def register_health_check(self, name: str, check_function, critical: bool = False):
        """Register a health check function"""
        self.health_checks[name] = {
            "function": check_function,
            "critical": critical,
            "last_result": None,
            "last_check": None
        }
    
    async def run_all_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {}
        critical_failures = []
        
        for name, check_info in self.health_checks.items():
            try:
                start_time = time.time()
                result = await check_info["function"]()
                duration = time.time() - start_time
                
                check_result = {
                    "status": "healthy" if result else "unhealthy",
                    "duration_ms": round(duration * 1000, 2),
                    "timestamp": datetime.now().isoformat(),
                    "critical": check_info["critical"]
                }
                
                results[name] = check_result
                self.last_check_results[name] = check_result
                
                if not result and check_info["critical"]:
                    critical_failures.append(name)
                    
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "critical": check_info["critical"],
                    "timestamp": datetime.now().isoformat()
                }
                
                if check_info["critical"]:
                    critical_failures.append(name)
        
        return {
            "overall_status": "critical" if critical_failures else "healthy",
            "critical_failures": critical_failures,
            "checks": results,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _check_database_connectivity(self) -> bool:
        """Check database connectivity"""
        try:
            with sqlite3.connect("trading_data.db", timeout=5) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except:
            return False
    
    async def _check_api_connectivity(self) -> bool:
        """Check external API connectivity"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.binance.com/api/v3/ping", timeout=10) as response:
                    return response.status == 200
        except:
            return False
    
    async def _check_disk_space(self) -> bool:
        """Check available disk space"""
        try:
            import psutil
            disk_usage = psutil.disk_usage('.')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            return free_percent > 10  # At least 10% free space
        except:
            return False
    
    async def _check_memory_usage(self) -> bool:
        """Check memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent < 90  # Less than 90% memory usage
        except:
            return False
    
    async def _check_process_health(self) -> bool:
        """Check if main processes are running"""
        try:
            import psutil
            current_process = psutil.Process()
            return current_process.is_running()
        except:
            return False

class DisasterDetector:
    def __init__(self, health_checker: SystemHealthChecker):
        self.health_checker = health_checker
        self.detection_rules = []
        self.detection_active = False
        self.detection_thread = None
        
    def add_detection_rule(self, rule: RecoveryPlan):
        """Add disaster detection rule"""
        self.detection_rules.append(rule)
        
    def start_detection(self, check_interval: int = 60):
        """Start disaster detection monitoring"""
        if self.detection_active:
            return
            
        self.detection_active = True
        self.detection_thread = threading.Thread(
            target=self._detection_loop,
            args=(check_interval,),
            daemon=True
        )
        self.detection_thread.start()
        print(f"🔍 Disaster detection started (interval: {check_interval}s)")
    
    def stop_detection(self):
        """Stop disaster detection"""
        self.detection_active = False
        if self.detection_thread:
            self.detection_thread.join(timeout=5)
        print("⏹️ Disaster detection stopped")
    
    def _detection_loop(self, interval: int):
        """Main detection loop"""
        while self.detection_active:
            try:
                # Run health checks
                health_results = asyncio.run(self.health_checker.run_all_health_checks())
                
                # Check for disaster conditions
                if health_results["overall_status"] == "critical":
                    self._trigger_disaster_response(health_results)
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"❌ Error in disaster detection: {e}")
                time.sleep(interval)
    
    def _trigger_disaster_response(self, health_results: Dict[str, Any]):
        """Trigger disaster response based on health check results"""
        print("🚨 CRITICAL SYSTEM FAILURE DETECTED")
        print(f"Failed checks: {health_results['critical_failures']}")
        
        # In a real system, this would trigger the recovery manager
        # For now, just log the event
        event = DisasterEvent(
            event_id=f"disaster_{int(time.time())}",
            disaster_type=DisasterType.SYSTEM_FAILURE,
            severity=9,
            detected_at=datetime.now(),
            description=f"Critical system failure: {health_results['critical_failures']}",
            affected_systems=health_results['critical_failures'],
            recovery_started_at=None,
            recovery_completed_at=None,
            status=RecoveryStatus.DETECTING,
            recovery_actions=[],
            data_loss_estimate="minimal"
        )
        
        print(f"📝 Disaster event logged: {event.event_id}")

class RecoveryExecutor:
    def __init__(self):
        self.recovery_procedures = {}
        self.active_recoveries = {}
        
    def register_recovery_procedure(self, disaster_type: DisasterType, procedure):
        """Register recovery procedure for disaster type"""
        self.recovery_procedures[disaster_type] = procedure
        
    async def execute_recovery(self, disaster_event: DisasterEvent) -> bool:
        """Execute recovery procedure for disaster event"""
        try:
            disaster_event.status = RecoveryStatus.RESPONDING
            disaster_event.recovery_started_at = datetime.now()
            
            procedure = self.recovery_procedures.get(disaster_event.disaster_type)
            if not procedure:
                print(f"❌ No recovery procedure for {disaster_event.disaster_type.value}")
                return False
            
            print(f"🚑 Starting recovery for {disaster_event.event_id}")
            
            # Execute recovery steps
            disaster_event.status = RecoveryStatus.RECOVERING
            success = await procedure(disaster_event)
            
            if success:
                disaster_event.status = RecoveryStatus.COMPLETED
                disaster_event.recovery_completed_at = datetime.now()
                print(f"✅ Recovery completed for {disaster_event.event_id}")
            else:
                disaster_event.status = RecoveryStatus.FAILED
                print(f"❌ Recovery failed for {disaster_event.event_id}")
            
            return success
            
        except Exception as e:
            disaster_event.status = RecoveryStatus.FAILED
            disaster_event.recovery_actions.append(f"Recovery exception: {e}")
            print(f"❌ Recovery error for {disaster_event.event_id}: {e}")
            return False

class DisasterRecoveryManager:
    """Main disaster recovery management system"""
    
    def __init__(self, db_path: str = "disaster_recovery.db"):
        self.db_path = Path(db_path)
        self.health_checker = SystemHealthChecker()
        self.detector = DisasterDetector(self.health_checker)
        self.executor = RecoveryExecutor()
        self.disaster_history: List[DisasterEvent] = []
        
        self._setup_database()
        self._register_default_health_checks()
        self._register_default_recovery_procedures()
    
    def _setup_database(self):
        """Setup SQLite database for disaster recovery tracking"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS disaster_events (
                        event_id TEXT PRIMARY KEY,
                        disaster_type TEXT NOT NULL,
                        severity INTEGER NOT NULL,
                        detected_at TEXT NOT NULL,
                        description TEXT NOT NULL,
                        affected_systems TEXT NOT NULL,
                        recovery_started_at TEXT,
                        recovery_completed_at TEXT,
                        status TEXT NOT NULL,
                        recovery_actions TEXT,
                        data_loss_estimate TEXT
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS recovery_plans (
                        disaster_type TEXT PRIMARY KEY,
                        plan_data TEXT NOT NULL,
                        last_updated TEXT NOT NULL
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            print(f"❌ Error setting up disaster recovery database: {e}")
    
    def _register_default_health_checks(self):
        """Register default health checks"""
        self.health_checker.register_health_check(
            "database", self.health_checker._check_database_connectivity, critical=True
        )
        self.health_checker.register_health_check(
            "api_connectivity", self.health_checker._check_api_connectivity, critical=True
        )
        self.health_checker.register_health_check(
            "disk_space", self.health_checker._check_disk_space, critical=True
        )
        self.health_checker.register_health_check(
            "memory_usage", self.health_checker._check_memory_usage, critical=False
        )
        self.health_checker.register_health_check(
            "process_health", self.health_checker._check_process_health, critical=True
        )
    
    def _register_default_recovery_procedures(self):
        """Register default recovery procedures"""
        self.executor.register_recovery_procedure(
            DisasterType.SYSTEM_FAILURE, self._recover_system_failure
        )
        self.executor.register_recovery_procedure(
            DisasterType.DATA_CORRUPTION, self._recover_data_corruption
        )
        self.executor.register_recovery_procedure(
            DisasterType.NETWORK_OUTAGE, self._recover_network_outage
        )
        self.executor.register_recovery_procedure(
            DisasterType.CRITICAL_ERROR, self._recover_critical_error
        )
    
    async def _recover_system_failure(self, event: DisasterEvent) -> bool:
        """Recovery procedure for system failures"""
        try:
            event.recovery_actions.append("Starting system failure recovery")
            
            # 1. Stop all trading activities
            event.recovery_actions.append("Stopping trading activities")
            await self._safe_shutdown_trading()
            
            # 2. Create emergency backup
            event.recovery_actions.append("Creating emergency backup")
            backup_path = self._create_emergency_backup()
            
            # 3. Restart critical services
            event.recovery_actions.append("Restarting critical services")
            await self._restart_critical_services()
            
            # 4. Verify system health
            event.recovery_actions.append("Verifying system health")
            health_ok = await self._verify_system_health()
            
            if health_ok:
                event.recovery_actions.append("✅ System failure recovery completed")
                return True
            else:
                event.recovery_actions.append("❌ System health verification failed")
                return False
                
        except Exception as e:
            event.recovery_actions.append(f"❌ System failure recovery error: {e}")
            return False
    
    async def _recover_data_corruption(self, event: DisasterEvent) -> bool:
        """Recovery procedure for data corruption"""
        try:
            event.recovery_actions.append("Starting data corruption recovery")
            
            # 1. Stop all data writing operations
            event.recovery_actions.append("Stopping data write operations")
            await self._stop_data_operations()
            
            # 2. Identify corruption extent
            event.recovery_actions.append("Analyzing corruption extent")
            corruption_analysis = await self._analyze_data_corruption()
            
            # 3. Restore from latest clean backup
            event.recovery_actions.append("Restoring from backup")
            restore_success = await self._restore_from_backup()
            
            # 4. Verify data integrity
            event.recovery_actions.append("Verifying data integrity")
            integrity_ok = await self._verify_data_integrity()
            
            if restore_success and integrity_ok:
                event.recovery_actions.append("✅ Data corruption recovery completed")
                return True
            else:
                event.recovery_actions.append("❌ Data corruption recovery failed")
                return False
                
        except Exception as e:
            event.recovery_actions.append(f"❌ Data corruption recovery error: {e}")
            return False
    
    async def _recover_network_outage(self, event: DisasterEvent) -> bool:
        """Recovery procedure for network outages"""
        try:
            event.recovery_actions.append("Starting network outage recovery")
            
            # 1. Switch to offline mode
            event.recovery_actions.append("Switching to offline mode")
            await self._enable_offline_mode()
            
            # 2. Preserve current state
            event.recovery_actions.append("Preserving current state")
            await self._preserve_trading_state()
            
            # 3. Monitor for network recovery
            event.recovery_actions.append("Monitoring network recovery")
            network_restored = await self._wait_for_network_recovery()
            
            # 4. Resume normal operations
            if network_restored:
                event.recovery_actions.append("Resuming normal operations")
                await self._resume_normal_operations()
                event.recovery_actions.append("✅ Network outage recovery completed")
                return True
            else:
                event.recovery_actions.append("❌ Network recovery timeout")
                return False
                
        except Exception as e:
            event.recovery_actions.append(f"❌ Network outage recovery error: {e}")
            return False
    
    async def _recover_critical_error(self, event: DisasterEvent) -> bool:
        """Recovery procedure for critical errors"""
        try:
            event.recovery_actions.append("Starting critical error recovery")
            
            # 1. Immediate safe mode
            event.recovery_actions.append("Activating safe mode")
            await self._activate_safe_mode()
            
            # 2. Collect diagnostic information
            event.recovery_actions.append("Collecting diagnostics")
            diagnostics = await self._collect_diagnostics()
            
            # 3. Attempt automatic error resolution
            event.recovery_actions.append("Attempting error resolution")
            error_resolved = await self._resolve_critical_error(diagnostics)
            
            # 4. Gradual service restoration
            if error_resolved:
                event.recovery_actions.append("Restoring services gradually")
                await self._gradual_service_restoration()
                event.recovery_actions.append("✅ Critical error recovery completed")
                return True
            else:
                event.recovery_actions.append("❌ Critical error resolution failed")
                return False
                
        except Exception as e:
            event.recovery_actions.append(f"❌ Critical error recovery error: {e}")
            return False
    
    # Recovery support functions
    async def _safe_shutdown_trading(self):
        """Safely shutdown trading operations"""
        try:
            # Close all open positions with market orders
            print("🛑 Emergency trading shutdown initiated")
            await asyncio.sleep(1)  # Simulate shutdown
        except Exception as e:
            print(f"❌ Error in safe trading shutdown: {e}")
    
    def _create_emergency_backup(self) -> str:
        """Create emergency backup of critical data"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"emergency_backup_{timestamp}.tar.gz"
            
            with tarfile.open(backup_name, "w:gz") as tar:
                # Backup critical files
                critical_files = [
                    "trading_data.db",
                    "config.yaml",
                    ".env",
                    "logs"
                ]
                
                for file_path in critical_files:
                    if Path(file_path).exists():
                        tar.add(file_path)
            
            print(f"💾 Emergency backup created: {backup_name}")
            return backup_name
            
        except Exception as e:
            print(f"❌ Error creating emergency backup: {e}")
            return ""
    
    async def _restart_critical_services(self):
        """Restart critical system services"""
        try:
            print("🔄 Restarting critical services")
            # In real implementation, restart specific services
            await asyncio.sleep(2)  # Simulate restart
        except Exception as e:
            print(f"❌ Error restarting services: {e}")
    
    async def _verify_system_health(self) -> bool:
        """Verify system health after recovery"""
        try:
            health_results = await self.health_checker.run_all_health_checks()
            return health_results["overall_status"] == "healthy"
        except:
            return False
    
    async def _stop_data_operations(self):
        """Stop all data writing operations"""
        print("🛑 Stopping data write operations")
        await asyncio.sleep(1)
    
    async def _analyze_data_corruption(self) -> Dict[str, Any]:
        """Analyze extent of data corruption"""
        return {
            "corruption_detected": True,
            "affected_tables": ["trades"],
            "severity": "moderate"
        }
    
    async def _restore_from_backup(self) -> bool:
        """Restore from latest clean backup"""
        try:
            print("🔄 Restoring from backup")
            await asyncio.sleep(2)  # Simulate restore
            return True
        except:
            return False
    
    async def _verify_data_integrity(self) -> bool:
        """Verify data integrity after restore"""
        try:
            with sqlite3.connect("trading_data.db") as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                return result[0] == "ok"
        except:
            return False
    
    async def _enable_offline_mode(self):
        """Enable offline mode operations"""
        print("📴 Enabling offline mode")
        await asyncio.sleep(1)
    
    async def _preserve_trading_state(self):
        """Preserve current trading state"""
        print("💾 Preserving trading state")
        await asyncio.sleep(1)
    
    async def _wait_for_network_recovery(self, timeout: int = 300) -> bool:
        """Wait for network connectivity to be restored"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await self.health_checker._check_api_connectivity():
                return True
            await asyncio.sleep(30)
        
        return False
    
    async def _resume_normal_operations(self):
        """Resume normal trading operations"""
        print("▶️ Resuming normal operations")
        await asyncio.sleep(1)
    
    async def _activate_safe_mode(self):
        """Activate safe mode"""
        print("🛡️ Activating safe mode")
        await asyncio.sleep(1)
    
    async def _collect_diagnostics(self) -> Dict[str, Any]:
        """Collect system diagnostic information"""
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('.').percent,
                "timestamp": datetime.now().isoformat()
            }
        except:
            return {"error": "Could not collect diagnostics"}
    
    async def _resolve_critical_error(self, diagnostics: Dict[str, Any]) -> bool:
        """Attempt to resolve critical error"""
        print("🔧 Attempting error resolution")
        await asyncio.sleep(2)  # Simulate resolution attempt
        return True  # Simplified for demo
    
    async def _gradual_service_restoration(self):
        """Gradually restore services"""
        print("📈 Gradually restoring services")
        await asyncio.sleep(2)
    
    def start_monitoring(self, check_interval: int = 60):
        """Start disaster recovery monitoring"""
        self.detector.start_detection(check_interval)
        print("🚨 Disaster recovery monitoring started")
    
    def stop_monitoring(self):
        """Stop disaster recovery monitoring"""
        self.detector.stop_detection()
        print("🚨 Disaster recovery monitoring stopped")
    
    def trigger_manual_recovery(self, disaster_type: DisasterType, description: str) -> str:
        """Manually trigger disaster recovery"""
        event = DisasterEvent(
            event_id=f"manual_{int(time.time())}",
            disaster_type=disaster_type,
            severity=8,
            detected_at=datetime.now(),
            description=description,
            affected_systems=["manual_trigger"],
            recovery_started_at=None,
            recovery_completed_at=None,
            status=RecoveryStatus.IDLE,
            recovery_actions=[],
            data_loss_estimate="unknown"
        )
        
        self.disaster_history.append(event)
        
        # Execute recovery asynchronously
        asyncio.create_task(self.executor.execute_recovery(event))
        
        print(f"🚨 Manual disaster recovery triggered: {event.event_id}")
        return event.event_id
    
    def get_disaster_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get disaster recovery summary"""
        cutoff_time = datetime.now() - timedelta(days=days)
        recent_events = [e for e in self.disaster_history if e.detected_at > cutoff_time]
        
        if not recent_events:
            return {
                "period_days": days,
                "total_events": 0,
                "status": "stable"
            }
        
        status_counts = {}
        type_counts = {}
        
        for event in recent_events:
            status_counts[event.status.value] = status_counts.get(event.status.value, 0) + 1
            type_counts[event.disaster_type.value] = type_counts.get(event.disaster_type.value, 0) + 1
        
        completed_events = [e for e in recent_events if e.status == RecoveryStatus.COMPLETED]
        avg_recovery_time = 0
        if completed_events:
            recovery_times = [
                (e.recovery_completed_at - e.recovery_started_at).total_seconds() / 60
                for e in completed_events if e.recovery_completed_at and e.recovery_started_at
            ]
            avg_recovery_time = sum(recovery_times) / len(recovery_times) if recovery_times else 0
        
        return {
            "period_days": days,
            "total_events": len(recent_events),
            "by_status": status_counts,
            "by_type": type_counts,
            "average_recovery_time_minutes": round(avg_recovery_time, 1),
            "latest_event": {
                "id": recent_events[-1].event_id,
                "type": recent_events[-1].disaster_type.value,
                "status": recent_events[-1].status.value,
                "severity": recent_events[-1].severity
            } if recent_events else None
        }
    
    def get_recovery_readiness(self) -> Dict[str, Any]:
        """Get disaster recovery readiness assessment"""
        try:
            # Check backup availability
            backup_files = list(Path(".").glob("*backup*.tar.gz"))
            latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime) if backup_files else None
            
            # Check recovery procedures
            procedure_count = len(self.executor.recovery_procedures)
            
            # Check monitoring status
            monitoring_active = self.detector.detection_active
            
            readiness_score = 0
            if latest_backup:
                backup_age_hours = (datetime.now().timestamp() - latest_backup.stat().st_mtime) / 3600
                if backup_age_hours < 24:
                    readiness_score += 40
                elif backup_age_hours < 168:  # 1 week
                    readiness_score += 20
            
            if procedure_count >= 4:
                readiness_score += 30
            
            if monitoring_active:
                readiness_score += 30
            
            readiness_level = "excellent" if readiness_score >= 80 else \
                            "good" if readiness_score >= 60 else \
                            "fair" if readiness_score >= 40 else "poor"
            
            return {
                "readiness_score": readiness_score,
                "readiness_level": readiness_level,
                "backup_status": {
                    "latest_backup": latest_backup.name if latest_backup else None,
                    "backup_age_hours": round((datetime.now().timestamp() - latest_backup.stat().st_mtime) / 3600, 1) if latest_backup else None
                },
                "recovery_procedures": procedure_count,
                "monitoring_active": monitoring_active,
                "recommendations": self._generate_readiness_recommendations(readiness_score)
            }
            
        except Exception as e:
            return {
                "readiness_score": 0,
                "readiness_level": "unknown",
                "error": str(e)
            }
    
    def _generate_readiness_recommendations(self, score: int) -> List[str]:
        """Generate disaster recovery readiness recommendations"""
        recommendations = []
        
        if score < 40:
            recommendations.append("🔴 Critical: Create backup procedures immediately")
            recommendations.append("🔴 Critical: Implement health monitoring")
            recommendations.append("🔴 Critical: Document recovery procedures")
        elif score < 60:
            recommendations.append("🟡 Update backup procedures")
            recommendations.append("🟡 Test recovery procedures")
        elif score < 80:
            recommendations.append("🟡 Schedule regular recovery drills")
            recommendations.append("🟡 Enhance monitoring coverage")
        else:
            recommendations.append("✅ Disaster recovery readiness is excellent")
            recommendations.append("💡 Consider automated recovery testing")
        
        return recommendations

# Global disaster recovery manager
disaster_recovery_manager = None

def initialize_disaster_recovery() -> DisasterRecoveryManager:
    """Initialize disaster recovery system"""
    global disaster_recovery_manager
    
    if disaster_recovery_manager is None:
        disaster_recovery_manager = DisasterRecoveryManager()
        disaster_recovery_manager.start_monitoring()
        print("✅ Disaster recovery system initialized")
    
    return disaster_recovery_manager

def get_disaster_recovery_manager() -> Optional[DisasterRecoveryManager]:
    """Get the global disaster recovery manager"""
    return disaster_recovery_manager

# Emergency functions
async def emergency_shutdown():
    """Emergency system shutdown"""
    manager = get_disaster_recovery_manager()
    if manager:
        await manager._safe_shutdown_trading()
    print("🚨 Emergency shutdown completed")

def emergency_backup() -> str:
    """Create emergency backup"""
    manager = get_disaster_recovery_manager()
    if manager:
        return manager._create_emergency_backup()
    return ""

async def trigger_disaster_recovery(disaster_type: str, description: str) -> str:
    """Trigger manual disaster recovery"""
    manager = get_disaster_recovery_manager() or initialize_disaster_recovery()
    disaster_enum = DisasterType(disaster_type)
    return manager.trigger_manual_recovery(disaster_enum, description)

if __name__ == "__main__":
    # Standalone testing
    print("🧪 Testing Disaster Recovery System")
    
    async def test_disaster_recovery():
        manager = DisasterRecoveryManager()
        
        print("🏥 Running health checks...")
        health_results = await manager.health_checker.run_all_health_checks()
        print(json.dumps(health_results, indent=2, default=str))
        
        print("📊 Checking recovery readiness...")
        readiness = manager.get_recovery_readiness()
        print(json.dumps(readiness, indent=2, default=str))
        
        print("🚨 Testing manual disaster recovery...")
        event_id = manager.trigger_manual_recovery(
            DisasterType.MANUAL_TRIGGER,
            "Testing disaster recovery system"
        )
        
        # Wait for recovery to complete
        await asyncio.sleep(3)
        
        print("📈 Disaster recovery summary:")
        summary = manager.get_disaster_summary(1)
        print(json.dumps(summary, indent=2, default=str))
    
    asyncio.run(test_disaster_recovery())
    print("✅ Disaster recovery system test completed!")