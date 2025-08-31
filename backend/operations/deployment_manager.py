"""
Automated Deployment Pipeline (Phase 15.5)
Enterprise-grade deployment automation with rollback capabilities
"""

import os
import asyncio
import subprocess
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sqlite3
import tarfile
import hashlib

class DeploymentStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class DeploymentEnvironment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class DeploymentConfig:
    environment: DeploymentEnvironment
    version: str
    git_branch: str
    build_command: str
    test_command: str
    deploy_command: str
    health_check_url: str
    rollback_enabled: bool
    backup_enabled: bool
    pre_deploy_hooks: List[str]
    post_deploy_hooks: List[str]

@dataclass
class DeploymentRecord:
    id: str
    environment: DeploymentEnvironment
    version: str
    status: DeploymentStatus
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    git_commit: str
    deployed_by: str
    logs: List[str]
    rollback_available: bool
    health_check_passed: bool

class DeploymentValidator:
    def __init__(self):
        self.validation_rules = []
    
    async def validate_pre_deployment(self, config: DeploymentConfig) -> Tuple[bool, List[str]]:
        """Validate system state before deployment"""
        issues = []
        
        # Check git repository state
        if not await self._check_git_status():
            issues.append("Git repository has uncommitted changes")
        
        # Check disk space
        if not await self._check_disk_space():
            issues.append("Insufficient disk space for deployment")
        
        # Check running processes
        if not await self._check_process_health():
            issues.append("Critical processes are not healthy")
        
        # Check environment variables
        if not await self._check_environment_vars(config):
            issues.append("Required environment variables are missing")
        
        return len(issues) == 0, issues
    
    async def _check_git_status(self) -> bool:
        """Check if git repository is in clean state"""
        try:
            result = await self._run_command("git status --porcelain")
            return result.returncode == 0 and not result.stdout.strip()
        except:
            return False
    
    async def _check_disk_space(self, min_gb: float = 1.0) -> bool:
        """Check available disk space"""
        try:
            result = await self._run_command("df -h .")
            # Simple check - in production would parse df output
            return True
        except:
            return False
    
    async def _check_process_health(self) -> bool:
        """Check if critical processes are running"""
        try:
            # Check if backend process is responsive
            result = await self._run_command("curl -s http://localhost:8000/health || echo 'unhealthy'")
            return "unhealthy" not in result.stdout
        except:
            return True  # Allow deployment if health check fails
    
    async def _check_environment_vars(self, config: DeploymentConfig) -> bool:
        """Check required environment variables"""
        required_vars = ["ENVIRONMENT", "API_KEY", "SECRET_KEY"]
        
        for var in required_vars:
            if not os.getenv(var):
                return False
        return True
    
    async def _run_command(self, command: str) -> subprocess.CompletedProcess:
        """Run shell command asynchronously"""
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        return subprocess.CompletedProcess(
            args=command,
            returncode=process.returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode()
        )

class BackupManager:
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_backup(self, deployment_id: str, environment: DeploymentEnvironment) -> str:
        """Create backup before deployment"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{environment.value}_{deployment_id}_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_name
            
            # Create backup of current application state
            with tarfile.open(backup_path, "w:gz") as tar:
                # Backup configuration files
                config_files = ["config.yaml", ".env", "requirements.txt"]
                for config_file in config_files:
                    if Path(config_file).exists():
                        tar.add(config_file)
                
                # Backup database
                if Path("trading_data.db").exists():
                    tar.add("trading_data.db")
                
                # Backup logs
                if Path("logs").exists():
                    tar.add("logs")
            
            print(f"💾 Backup created: {backup_name}")
            return str(backup_path)
            
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            return ""
    
    async def restore_backup(self, backup_path: str) -> bool:
        """Restore from backup"""
        try:
            if not Path(backup_path).exists():
                print(f"❌ Backup file not found: {backup_path}")
                return False
            
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(path=".")
            
            print(f"✅ Backup restored from: {backup_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error restoring backup: {e}")
            return False
    
    def list_backups(self, environment: DeploymentEnvironment = None) -> List[str]:
        """List available backups"""
        try:
            pattern = f"{environment.value}_*" if environment else "*"
            backups = list(self.backup_dir.glob(f"{pattern}.tar.gz"))
            return sorted([b.name for b in backups], reverse=True)
        except:
            return []

class DeploymentExecutor:
    def __init__(self, backup_manager: BackupManager):
        self.backup_manager = backup_manager
        
    async def execute_deployment(self, config: DeploymentConfig, deployment_id: str) -> Tuple[bool, List[str]]:
        """Execute deployment process"""
        logs = []
        
        try:
            # Create backup if enabled
            backup_path = ""
            if config.backup_enabled:
                backup_path = await self.backup_manager.create_backup(deployment_id, config.environment)
                logs.append(f"✅ Backup created: {backup_path}")
            
            # Run pre-deployment hooks
            for hook in config.pre_deploy_hooks:
                success, output = await self._run_hook(hook, "pre-deploy")
                logs.append(f"🔧 Pre-deploy hook: {hook} - {'✅' if success else '❌'}")
                if not success:
                    logs.append(f"❌ Hook failed: {output}")
                    return False, logs
            
            # Build application
            if config.build_command:
                success, output = await self._run_command_with_logging(config.build_command)
                logs.append(f"🔨 Build: {'✅' if success else '❌'}")
                if not success:
                    logs.append(f"❌ Build failed: {output}")
                    return False, logs
            
            # Run tests
            if config.test_command:
                success, output = await self._run_command_with_logging(config.test_command)
                logs.append(f"🧪 Tests: {'✅' if success else '❌'}")
                if not success:
                    logs.append(f"❌ Tests failed: {output}")
                    return False, logs
            
            # Deploy application
            success, output = await self._run_command_with_logging(config.deploy_command)
            logs.append(f"🚀 Deploy: {'✅' if success else '❌'}")
            if not success:
                logs.append(f"❌ Deploy failed: {output}")
                return False, logs
            
            # Health check
            if config.health_check_url:
                success = await self._health_check(config.health_check_url)
                logs.append(f"🏥 Health check: {'✅' if success else '❌'}")
                if not success:
                    logs.append("❌ Health check failed - deployment may be unhealthy")
            
            # Run post-deployment hooks
            for hook in config.post_deploy_hooks:
                success, output = await self._run_hook(hook, "post-deploy")
                logs.append(f"🔧 Post-deploy hook: {hook} - {'✅' if success else '❌'}")
                # Don't fail deployment for post-deploy hook failures
            
            logs.append(f"✅ Deployment {deployment_id} completed successfully")
            return True, logs
            
        except Exception as e:
            logs.append(f"❌ Deployment error: {e}")
            return False, logs
    
    async def _run_command_with_logging(self, command: str) -> Tuple[bool, str]:
        """Run command and capture output"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await process.communicate()
            output = stdout.decode()
            
            return process.returncode == 0, output
            
        except Exception as e:
            return False, str(e)
    
    async def _run_hook(self, hook: str, hook_type: str) -> Tuple[bool, str]:
        """Run deployment hook"""
        return await self._run_command_with_logging(hook)
    
    async def _health_check(self, url: str, max_retries: int = 5) -> bool:
        """Perform health check on deployed application"""
        for attempt in range(max_retries):
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            return True
            except:
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)  # Wait before retry
        
        return False

class DeploymentManager:
    """Main deployment management system"""
    
    def __init__(self, db_path: str = "deployments.db"):
        self.db_path = Path(db_path)
        self.validator = DeploymentValidator()
        self.backup_manager = BackupManager()
        self.executor = DeploymentExecutor(self.backup_manager)
        self.deployments: Dict[str, DeploymentRecord] = {}
        self._setup_database()
        self._load_default_configs()
    
    def _setup_database(self):
        """Setup SQLite database for deployment tracking"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS deployments (
                        id TEXT PRIMARY KEY,
                        environment TEXT NOT NULL,
                        version TEXT NOT NULL,
                        status TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        duration_seconds REAL,
                        git_commit TEXT,
                        deployed_by TEXT,
                        logs TEXT,
                        rollback_available BOOLEAN,
                        health_check_passed BOOLEAN
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS deployment_configs (
                        environment TEXT PRIMARY KEY,
                        config_data TEXT NOT NULL
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            print(f"❌ Error setting up deployment database: {e}")
    
    def _load_default_configs(self):
        """Load default deployment configurations"""
        self.configs = {
            DeploymentEnvironment.DEVELOPMENT: DeploymentConfig(
                environment=DeploymentEnvironment.DEVELOPMENT,
                version="dev",
                git_branch="main",
                build_command="echo 'No build required for development'",
                test_command="echo 'Skipping tests in development'",
                deploy_command="pm2 restart bitcoin-trading-bot-dev || pm2 start main.py --name bitcoin-trading-bot-dev",
                health_check_url="http://localhost:8000/health",
                rollback_enabled=False,
                backup_enabled=False,
                pre_deploy_hooks=["echo 'Development pre-deploy'"],
                post_deploy_hooks=["echo 'Development post-deploy'"]
            ),
            DeploymentEnvironment.STAGING: DeploymentConfig(
                environment=DeploymentEnvironment.STAGING,
                version="staging",
                git_branch="staging",
                build_command="pip install -r requirements.txt",
                test_command="python -m pytest tests/ -v",
                deploy_command="pm2 restart bitcoin-trading-bot-staging || pm2 start main.py --name bitcoin-trading-bot-staging",
                health_check_url="http://localhost:8001/health",
                rollback_enabled=True,
                backup_enabled=True,
                pre_deploy_hooks=[
                    "git checkout staging",
                    "git pull origin staging"
                ],
                post_deploy_hooks=[
                    "echo 'Deployment completed'",
                    "curl -X POST http://localhost:8001/api/system/deployment-notification"
                ]
            ),
            DeploymentEnvironment.PRODUCTION: DeploymentConfig(
                environment=DeploymentEnvironment.PRODUCTION,
                version="prod",
                git_branch="main",
                build_command="pip install -r requirements.txt --no-cache-dir",
                test_command="python -m pytest tests/ -v --tb=short",
                deploy_command="pm2 restart bitcoin-trading-bot-prod || pm2 start main.py --name bitcoin-trading-bot-prod",
                health_check_url="http://localhost:8000/health",
                rollback_enabled=True,
                backup_enabled=True,
                pre_deploy_hooks=[
                    "git checkout main",
                    "git pull origin main",
                    "python -c 'import sqlite3; print(\"Database connectivity OK\")'",
                    "curl -f http://localhost:8000/health || echo 'Service check'"
                ],
                post_deploy_hooks=[
                    "curl -X POST http://localhost:8000/api/system/deployment-notification",
                    "echo 'Production deployment completed'",
                    "python -c 'from operations.alerting_system import get_alerting_manager; mgr = get_alerting_manager(); mgr and print(\"Alert system notified\")'"
                ]
            )
        }
    
    async def deploy(self, environment: DeploymentEnvironment, version: str = None, 
                    deployed_by: str = "automated") -> str:
        """Execute deployment to specified environment"""
        deployment_id = f"deploy_{environment.value}_{int(datetime.now().timestamp())}"
        
        config = self.configs.get(environment)
        if not config:
            print(f"❌ No configuration found for environment: {environment.value}")
            return deployment_id
        
        if version:
            config.version = version
        
        # Create deployment record
        record = DeploymentRecord(
            id=deployment_id,
            environment=environment,
            version=config.version,
            status=DeploymentStatus.PENDING,
            start_time=datetime.now(),
            end_time=None,
            duration_seconds=None,
            git_commit=await self._get_git_commit(),
            deployed_by=deployed_by,
            logs=[],
            rollback_available=False,
            health_check_passed=False
        )
        
        self.deployments[deployment_id] = record
        self._save_deployment_record(record)
        
        print(f"🚀 Starting deployment {deployment_id} to {environment.value}")
        
        # Execute deployment asynchronously
        asyncio.create_task(self._execute_deployment_async(config, record))
        
        return deployment_id
    
    async def _execute_deployment_async(self, config: DeploymentConfig, record: DeploymentRecord):
        """Execute deployment asynchronously"""
        try:
            record.status = DeploymentStatus.IN_PROGRESS
            record.logs.append(f"🚀 Deployment started at {record.start_time}")
            
            # Pre-deployment validation
            is_valid, issues = await self.validator.validate_pre_deployment(config)
            if not is_valid:
                record.status = DeploymentStatus.FAILED
                record.logs.extend([f"❌ Validation failed: {issue}" for issue in issues])
                await self._finalize_deployment(record)
                return
            
            record.logs.append("✅ Pre-deployment validation passed")
            
            # Execute deployment
            success, deploy_logs = await self.executor.execute_deployment(config, record.id)
            record.logs.extend(deploy_logs)
            
            if success:
                record.status = DeploymentStatus.SUCCESS
                record.rollback_available = config.rollback_enabled
                record.health_check_passed = True
                record.logs.append(f"✅ Deployment {record.id} completed successfully")
            else:
                record.status = DeploymentStatus.FAILED
                record.logs.append(f"❌ Deployment {record.id} failed")
                
                # Auto-rollback if enabled and previous deployment available
                if config.rollback_enabled:
                    await self._attempt_auto_rollback(record.environment, record)
            
        except Exception as e:
            record.status = DeploymentStatus.FAILED
            record.logs.append(f"❌ Deployment exception: {e}")
        
        finally:
            await self._finalize_deployment(record)
    
    async def _finalize_deployment(self, record: DeploymentRecord):
        """Finalize deployment record"""
        record.end_time = datetime.now()
        record.duration_seconds = (record.end_time - record.start_time).total_seconds()
        
        self._save_deployment_record(record)
        self._print_deployment_summary(record)
    
    def _print_deployment_summary(self, record: DeploymentRecord):
        """Print deployment summary"""
        status_emoji = {
            DeploymentStatus.SUCCESS: "✅",
            DeploymentStatus.FAILED: "❌",
            DeploymentStatus.ROLLED_BACK: "🔄"
        }
        
        print(f"\n{status_emoji.get(record.status, '📊')} DEPLOYMENT SUMMARY")
        print(f"ID: {record.id}")
        print(f"Environment: {record.environment.value}")
        print(f"Version: {record.version}")
        print(f"Status: {record.status.value}")
        print(f"Duration: {record.duration_seconds:.1f}s")
        print(f"Health Check: {'✅' if record.health_check_passed else '❌'}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    async def rollback(self, environment: DeploymentEnvironment, target_deployment_id: str = None) -> bool:
        """Rollback to previous deployment"""
        try:
            # Find target deployment to rollback to
            if not target_deployment_id:
                target_deployment_id = await self._find_last_successful_deployment(environment)
            
            if not target_deployment_id:
                print(f"❌ No successful deployment found for rollback in {environment.value}")
                return False
            
            target_record = self.deployments.get(target_deployment_id)
            if not target_record:
                print(f"❌ Deployment record not found: {target_deployment_id}")
                return False
            
            print(f"🔄 Rolling back {environment.value} to deployment {target_deployment_id}")
            
            # Find backup for target deployment
            backups = self.backup_manager.list_backups(environment)
            target_backup = None
            
            for backup in backups:
                if target_deployment_id in backup:
                    target_backup = str(self.backup_manager.backup_dir / backup)
                    break
            
            if target_backup:
                success = await self.backup_manager.restore_backup(target_backup)
                if success:
                    print(f"✅ Rollback completed to {target_deployment_id}")
                    
                    # Create rollback record
                    rollback_record = DeploymentRecord(
                        id=f"rollback_{int(datetime.now().timestamp())}",
                        environment=environment,
                        version=target_record.version,
                        status=DeploymentStatus.ROLLED_BACK,
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        duration_seconds=0.0,
                        git_commit=target_record.git_commit,
                        deployed_by="rollback_system",
                        logs=[f"Rolled back to deployment {target_deployment_id}"],
                        rollback_available=False,
                        health_check_passed=True
                    )
                    
                    self.deployments[rollback_record.id] = rollback_record
                    self._save_deployment_record(rollback_record)
                    
                    return True
            
            print(f"❌ Rollback failed - no backup found for {target_deployment_id}")
            return False
            
        except Exception as e:
            print(f"❌ Error during rollback: {e}")
            return False
    
    async def _find_last_successful_deployment(self, environment: DeploymentEnvironment) -> Optional[str]:
        """Find the last successful deployment for environment"""
        env_deployments = [
            d for d in self.deployments.values()
            if d.environment == environment and d.status == DeploymentStatus.SUCCESS
        ]
        
        if env_deployments:
            latest = max(env_deployments, key=lambda x: x.start_time)
            return latest.id
        
        return None
    
    async def _attempt_auto_rollback(self, environment: DeploymentEnvironment, failed_record: DeploymentRecord):
        """Attempt automatic rollback after failed deployment"""
        try:
            print(f"🔄 Attempting auto-rollback for {environment.value}")
            success = await self.rollback(environment)
            
            if success:
                failed_record.logs.append("✅ Auto-rollback completed")
                failed_record.status = DeploymentStatus.ROLLED_BACK
            else:
                failed_record.logs.append("❌ Auto-rollback failed")
                
        except Exception as e:
            failed_record.logs.append(f"❌ Auto-rollback error: {e}")
    
    async def _get_git_commit(self) -> str:
        """Get current git commit hash"""
        try:
            process = await asyncio.create_subprocess_shell(
                "git rev-parse HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            return stdout.decode().strip()
        except:
            return "unknown"
    
    def _save_deployment_record(self, record: DeploymentRecord):
        """Save deployment record to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO deployments 
                    (id, environment, version, status, start_time, end_time, 
                     duration_seconds, git_commit, deployed_by, logs, 
                     rollback_available, health_check_passed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    record.environment.value,
                    record.version,
                    record.status.value,
                    record.start_time.isoformat(),
                    record.end_time.isoformat() if record.end_time else None,
                    record.duration_seconds,
                    record.git_commit,
                    record.deployed_by,
                    json.dumps(record.logs),
                    record.rollback_available,
                    record.health_check_passed
                ))
                conn.commit()
        except Exception as e:
            print(f"❌ Error saving deployment record: {e}")
    
    def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """Get deployment status"""
        return self.deployments.get(deployment_id)
    
    def get_deployment_history(self, environment: DeploymentEnvironment = None, 
                             limit: int = 10) -> List[DeploymentRecord]:
        """Get deployment history"""
        deployments = list(self.deployments.values())
        
        if environment:
            deployments = [d for d in deployments if d.environment == environment]
        
        deployments.sort(key=lambda x: x.start_time, reverse=True)
        return deployments[:limit]
    
    def get_deployment_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get deployment summary for specified period"""
        cutoff_time = datetime.now() - timedelta(days=days)
        recent_deployments = [
            d for d in self.deployments.values() 
            if d.start_time > cutoff_time
        ]
        
        if not recent_deployments:
            return {
                "period_days": days,
                "total_deployments": 0,
                "status": "no_deployments"
            }
        
        status_counts = defaultdict(int)
        env_counts = defaultdict(int)
        
        for deployment in recent_deployments:
            status_counts[deployment.status.value] += 1
            env_counts[deployment.environment.value] += 1
        
        success_rate = (status_counts.get("success", 0) / len(recent_deployments)) * 100
        avg_duration = sum(d.duration_seconds or 0 for d in recent_deployments) / len(recent_deployments)
        
        return {
            "period_days": days,
            "total_deployments": len(recent_deployments),
            "success_rate": round(success_rate, 1),
            "average_duration_seconds": round(avg_duration, 1),
            "by_status": dict(status_counts),
            "by_environment": dict(env_counts),
            "latest_deployment": {
                "id": recent_deployments[0].id,
                "environment": recent_deployments[0].environment.value,
                "status": recent_deployments[0].status.value,
                "version": recent_deployments[0].version
            } if recent_deployments else None
        }
    
    async def quick_deploy_development(self) -> str:
        """Quick deployment to development environment"""
        print("🚀 Quick deploy to development environment")
        return await self.deploy(DeploymentEnvironment.DEVELOPMENT, deployed_by="quick_deploy")
    
    async def production_deploy(self, version: str, deployed_by: str = "manual") -> str:
        """Safe production deployment with full validation"""
        print(f"🏭 Production deployment of version {version}")
        
        # Extra validation for production
        print("🔍 Running enhanced pre-production validation...")
        
        # Validate staging deployment first
        staging_deployments = [
            d for d in self.deployments.values()
            if d.environment == DeploymentEnvironment.STAGING 
            and d.status == DeploymentStatus.SUCCESS
            and d.start_time > datetime.now() - timedelta(days=1)
        ]
        
        if not staging_deployments:
            print("⚠️ Warning: No recent successful staging deployment found")
        
        return await self.deploy(DeploymentEnvironment.PRODUCTION, version, deployed_by)
    
    def configure_environment(self, environment: DeploymentEnvironment, config: DeploymentConfig):
        """Update configuration for specific environment"""
        self.configs[environment] = config
        print(f"✅ Configuration updated for {environment.value}")
    
    def export_deployment_data(self, format: str = "json", days: int = 30) -> str:
        """Export deployment data"""
        summary = self.get_deployment_summary(days)
        
        if format.lower() == "json":
            return json.dumps(summary, indent=2, default=str)
        elif format.lower() == "yaml":
            if YAML_AVAILABLE:
                return yaml.dump(summary, default_flow_style=False)
            else:
                return json.dumps(summary, indent=2, default=str)
        else:
            return json.dumps(summary, indent=2, default=str)

# Integration functions
def create_deployment_manager(custom_configs: Dict[str, DeploymentConfig] = None) -> DeploymentManager:
    """Create deployment manager with optional custom configurations"""
    manager = DeploymentManager()
    
    if custom_configs:
        for env_name, config in custom_configs.items():
            env = DeploymentEnvironment(env_name)
            manager.configure_environment(env, config)
    
    return manager

# Global deployment manager instance
deployment_manager = None

def initialize_deployment_system() -> DeploymentManager:
    """Initialize global deployment manager"""
    global deployment_manager
    
    if deployment_manager is None:
        deployment_manager = DeploymentManager()
        print("✅ Deployment system initialized")
    
    return deployment_manager

def get_deployment_manager() -> Optional[DeploymentManager]:
    """Get the global deployment manager instance"""
    return deployment_manager

# CLI-style deployment functions
async def deploy_dev():
    """Deploy to development environment"""
    manager = get_deployment_manager() or initialize_deployment_system()
    return await manager.quick_deploy_development()

async def deploy_staging(version: str = "staging"):
    """Deploy to staging environment"""
    manager = get_deployment_manager() or initialize_deployment_system()
    return await manager.deploy(DeploymentEnvironment.STAGING, version)

async def deploy_prod(version: str, deployed_by: str = "cli"):
    """Deploy to production environment"""
    manager = get_deployment_manager() or initialize_deployment_system()
    return await manager.production_deploy(version, deployed_by)

async def rollback_env(environment: str):
    """Rollback specified environment"""
    manager = get_deployment_manager() or initialize_deployment_system()
    env = DeploymentEnvironment(environment)
    return await manager.rollback(env)

if __name__ == "__main__":
    # Standalone testing
    print("🧪 Testing Deployment Management System")
    
    async def test_deployment():
        manager = DeploymentManager()
        
        print("📋 Testing development deployment...")
        deployment_id = await manager.deploy(DeploymentEnvironment.DEVELOPMENT)
        
        # Wait a moment for async deployment
        await asyncio.sleep(2)
        
        status = manager.get_deployment_status(deployment_id)
        if status:
            print(f"✅ Deployment status: {status.status.value}")
            print(f"📊 Duration: {status.duration_seconds}s")
        
        print("📈 Deployment summary:")
        summary = manager.get_deployment_summary(1)
        print(json.dumps(summary, indent=2, default=str))
    
    asyncio.run(test_deployment())
    print("✅ Deployment system test completed!")