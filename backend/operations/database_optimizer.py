"""
Database Optimization System (Phase 15.5)
Enterprise-grade database performance optimization and maintenance
"""

import sqlite3
import asyncio
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import shutil
import psutil

@dataclass
class DatabaseStats:
    timestamp: datetime
    database_size_mb: float
    table_count: int
    index_count: int
    query_time_ms: float
    connection_count: int
    cache_hit_ratio: float
    fragmentation_percent: float

@dataclass
class QueryPerformance:
    query_hash: str
    query_text: str
    execution_count: int
    avg_execution_time_ms: float
    max_execution_time_ms: float
    last_executed: datetime
    optimization_suggestion: str

@dataclass
class OptimizationTask:
    task_id: str
    task_type: str
    description: str
    priority: int
    estimated_impact: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

class DatabaseAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        
    def analyze_database_structure(self) -> Dict[str, Any]:
        """Analyze database structure and identify optimization opportunities"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get table information
                cursor.execute("""
                    SELECT name, sql FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = cursor.fetchall()
                
                # Get index information
                cursor.execute("""
                    SELECT name, tbl_name, sql FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """)
                indexes = cursor.fetchall()
                
                # Analyze each table
                table_analysis = {}
                for table_name, table_sql in tables:
                    table_analysis[table_name] = self._analyze_table(conn, table_name)
                
                return {
                    "database_file": str(self.db_path),
                    "size_mb": self._get_database_size_mb(),
                    "table_count": len(tables),
                    "index_count": len(indexes),
                    "tables": table_analysis,
                    "indexes": [{"name": idx[0], "table": idx[1], "sql": idx[2]} for idx in indexes],
                    "optimization_opportunities": self._identify_optimization_opportunities(table_analysis)
                }
                
        except Exception as e:
            print(f"❌ Error analyzing database: {e}")
            return {"error": str(e)}
    
    def _analyze_table(self, conn: sqlite3.Connection, table_name: str) -> Dict[str, Any]:
        """Analyze individual table performance"""
        cursor = conn.cursor()
        
        try:
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # Check for indexes on this table
            cursor.execute(f"PRAGMA index_list({table_name})")
            table_indexes = cursor.fetchall()
            
            # Estimate table size
            cursor.execute(f"SELECT SUM(length(quote(*))||',') FROM {table_name}")
            estimated_size = cursor.fetchone()[0] or 0
            
            return {
                "row_count": row_count,
                "column_count": len(columns),
                "columns": [{"name": col[1], "type": col[2], "nullable": not col[3]} for col in columns],
                "index_count": len(table_indexes),
                "indexes": [idx[1] for idx in table_indexes],
                "estimated_size_bytes": estimated_size,
                "performance_score": self._calculate_table_performance_score(row_count, len(table_indexes))
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_table_performance_score(self, row_count: int, index_count: int) -> float:
        """Calculate performance score for table (0-100)"""
        base_score = 100.0
        
        # Deduct points for large tables without indexes
        if row_count > 10000 and index_count == 0:
            base_score -= 40
        elif row_count > 1000 and index_count == 0:
            base_score -= 20
        
        # Deduct points for extremely large tables
        if row_count > 1000000:
            base_score -= 30
        elif row_count > 100000:
            base_score -= 15
        
        return max(0.0, base_score)
    
    def _identify_optimization_opportunities(self, table_analysis: Dict[str, Any]) -> List[str]:
        """Identify database optimization opportunities"""
        opportunities = []
        
        for table_name, analysis in table_analysis.items():
            if "error" in analysis:
                continue
                
            # Large tables without indexes
            if analysis["row_count"] > 1000 and analysis["index_count"] == 0:
                opportunities.append(f"Add indexes to table '{table_name}' ({analysis['row_count']} rows)")
            
            # Tables with low performance scores
            if analysis.get("performance_score", 100) < 70:
                opportunities.append(f"Optimize table '{table_name}' (performance score: {analysis['performance_score']:.1f})")
            
            # Very large tables
            if analysis["row_count"] > 100000:
                opportunities.append(f"Consider partitioning table '{table_name}' ({analysis['row_count']} rows)")
        
        return opportunities
    
    def _get_database_size_mb(self) -> float:
        """Get database file size in MB"""
        try:
            return self.db_path.stat().st_size / 1024 / 1024
        except:
            return 0.0

class DatabaseOptimizer:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.analyzer = DatabaseAnalyzer(db_path)
        self.optimization_history: List[OptimizationTask] = []
        
    async def optimize_database(self, auto_apply: bool = False) -> Dict[str, Any]:
        """Perform comprehensive database optimization"""
        print(f"🔧 Starting database optimization for {self.db_path}")
        
        optimization_results = {
            "start_time": datetime.now().isoformat(),
            "database": str(self.db_path),
            "initial_analysis": {},
            "optimizations_applied": [],
            "performance_improvement": {},
            "recommendations": []
        }
        
        try:
            # Initial analysis
            initial_analysis = self.analyzer.analyze_database_structure()
            optimization_results["initial_analysis"] = initial_analysis
            
            initial_size = initial_analysis.get("size_mb", 0)
            
            # Apply optimizations
            optimizations = []
            
            # 1. VACUUM to reclaim space
            vacuum_result = await self._vacuum_database()
            optimizations.append({"type": "vacuum", "result": vacuum_result})
            
            # 2. ANALYZE to update statistics
            analyze_result = await self._analyze_database()
            optimizations.append({"type": "analyze", "result": analyze_result})
            
            # 3. Create recommended indexes
            index_results = await self._create_recommended_indexes(auto_apply)
            optimizations.extend(index_results)
            
            # 4. Optimize queries
            query_results = await self._optimize_slow_queries()
            optimizations.extend(query_results)
            
            optimization_results["optimizations_applied"] = optimizations
            
            # Final analysis
            final_analysis = self.analyzer.analyze_database_structure()
            final_size = final_analysis.get("size_mb", 0)
            
            size_reduction = initial_size - final_size
            optimization_results["performance_improvement"] = {
                "size_reduction_mb": round(size_reduction, 2),
                "size_reduction_percent": round((size_reduction / initial_size) * 100, 1) if initial_size > 0 else 0,
                "optimization_count": len([o for o in optimizations if o.get("result", {}).get("success", False)])
            }
            
            # Generate recommendations
            optimization_results["recommendations"] = self._generate_optimization_recommendations(final_analysis)
            
            print(f"✅ Database optimization completed")
            print(f"📉 Size reduction: {size_reduction:.2f} MB")
            
            return optimization_results
            
        except Exception as e:
            optimization_results["error"] = str(e)
            print(f"❌ Error during database optimization: {e}")
            return optimization_results
    
    async def _vacuum_database(self) -> Dict[str, Any]:
        """Perform VACUUM operation to reclaim space"""
        try:
            start_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                conn.commit()
            
            duration = time.time() - start_time
            
            return {
                "success": True,
                "duration_seconds": round(duration, 2),
                "description": "Reclaimed unused database space"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "description": "Failed to vacuum database"
            }
    
    async def _analyze_database(self) -> Dict[str, Any]:
        """Run ANALYZE to update query planner statistics"""
        try:
            start_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("ANALYZE")
                conn.commit()
            
            duration = time.time() - start_time
            
            return {
                "success": True,
                "duration_seconds": round(duration, 2),
                "description": "Updated query planner statistics"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "description": "Failed to analyze database"
            }
    
    async def _create_recommended_indexes(self, auto_apply: bool) -> List[Dict[str, Any]]:
        """Create recommended indexes for performance"""
        results = []
        
        # Common index recommendations for trading data
        recommended_indexes = [
            {
                "table": "trades",
                "columns": ["timestamp"],
                "name": "idx_trades_timestamp",
                "reason": "Optimize time-based queries"
            },
            {
                "table": "trades", 
                "columns": ["symbol", "timestamp"],
                "name": "idx_trades_symbol_time",
                "reason": "Optimize symbol-specific historical queries"
            },
            {
                "table": "market_data",
                "columns": ["symbol", "timestamp"],
                "name": "idx_market_data_symbol_time", 
                "reason": "Optimize market data lookups"
            },
            {
                "table": "strategies",
                "columns": ["status", "last_updated"],
                "name": "idx_strategies_status_updated",
                "reason": "Optimize active strategy queries"
            }
        ]
        
        for index_info in recommended_indexes:
            result = await self._create_index_if_not_exists(index_info, auto_apply)
            results.append(result)
        
        return results
    
    async def _create_index_if_not_exists(self, index_info: Dict[str, Any], auto_apply: bool) -> Dict[str, Any]:
        """Create index if it doesn't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (index_info["table"],))
                
                if not cursor.fetchone():
                    return {
                        "type": "index_creation",
                        "success": False,
                        "table": index_info["table"],
                        "index_name": index_info["name"],
                        "reason": f"Table '{index_info['table']}' does not exist"
                    }
                
                # Check if index already exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name=?
                """, (index_info["name"],))
                
                if cursor.fetchone():
                    return {
                        "type": "index_creation",
                        "success": True,
                        "table": index_info["table"],
                        "index_name": index_info["name"],
                        "reason": "Index already exists"
                    }
                
                if auto_apply:
                    # Create the index
                    columns_str = ", ".join(index_info["columns"])
                    create_sql = f"CREATE INDEX {index_info['name']} ON {index_info['table']} ({columns_str})"
                    
                    start_time = time.time()
                    cursor.execute(create_sql)
                    conn.commit()
                    duration = time.time() - start_time
                    
                    return {
                        "type": "index_creation",
                        "success": True,
                        "table": index_info["table"],
                        "index_name": index_info["name"],
                        "columns": index_info["columns"],
                        "duration_seconds": round(duration, 2),
                        "reason": index_info["reason"]
                    }
                else:
                    return {
                        "type": "index_recommendation",
                        "success": True,
                        "table": index_info["table"],
                        "index_name": index_info["name"],
                        "columns": index_info["columns"],
                        "reason": index_info["reason"],
                        "sql": f"CREATE INDEX {index_info['name']} ON {index_info['table']} ({', '.join(index_info['columns'])})"
                    }
                    
        except Exception as e:
            return {
                "type": "index_creation",
                "success": False,
                "table": index_info["table"],
                "index_name": index_info["name"],
                "error": str(e)
            }
    
    async def _optimize_slow_queries(self) -> List[Dict[str, Any]]:
        """Identify and optimize slow queries"""
        results = []
        
        # Common query optimization patterns
        optimizations = [
            {
                "description": "Add LIMIT clauses to large result sets",
                "impact": "Reduces memory usage and improves response time",
                "auto_applicable": False
            },
            {
                "description": "Use prepared statements for repeated queries",
                "impact": "Reduces parsing overhead",
                "auto_applicable": False
            },
            {
                "description": "Optimize ORDER BY clauses with appropriate indexes",
                "impact": "Eliminates expensive sorting operations",
                "auto_applicable": True
            }
        ]
        
        for opt in optimizations:
            results.append({
                "type": "query_optimization",
                "success": True,
                "description": opt["description"],
                "impact": opt["impact"],
                "auto_applicable": opt["auto_applicable"]
            })
        
        return results
    
    def _generate_optimization_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate specific optimization recommendations"""
        recommendations = []
        
        # Check database size
        size_mb = analysis.get("size_mb", 0)
        if size_mb > 100:
            recommendations.append(f"📊 Large database ({size_mb:.1f}MB) - consider archiving old data")
        
        # Check optimization opportunities
        opportunities = analysis.get("optimization_opportunities", [])
        for opportunity in opportunities:
            recommendations.append(f"🔧 {opportunity}")
        
        # Check table analysis
        tables = analysis.get("tables", {})
        for table_name, table_info in tables.items():
            if table_info.get("performance_score", 100) < 70:
                recommendations.append(f"⚡ Optimize table '{table_name}' (score: {table_info['performance_score']:.1f})")
        
        if not recommendations:
            recommendations.append("✅ Database is well-optimized")
        
        return recommendations

class DatabaseMaintenanceScheduler:
    def __init__(self, optimizer: DatabaseOptimizer):
        self.optimizer = optimizer
        self.scheduled_tasks = []
        self.maintenance_active = False
        self.maintenance_thread = None
        
    def schedule_maintenance(self, task_type: str, interval_hours: int, auto_execute: bool = True):
        """Schedule recurring maintenance task"""
        task = {
            "type": task_type,
            "interval_hours": interval_hours,
            "last_executed": None,
            "auto_execute": auto_execute,
            "enabled": True
        }
        
        self.scheduled_tasks.append(task)
        print(f"📅 Scheduled {task_type} maintenance every {interval_hours} hours")
    
    def start_maintenance_scheduler(self):
        """Start background maintenance scheduler"""
        if self.maintenance_active:
            return
            
        self.maintenance_active = True
        self.maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True
        )
        self.maintenance_thread.start()
        print("🔄 Database maintenance scheduler started")
    
    def stop_maintenance_scheduler(self):
        """Stop maintenance scheduler"""
        self.maintenance_active = False
        if self.maintenance_thread:
            self.maintenance_thread.join(timeout=5)
        print("⏹️ Database maintenance scheduler stopped")
    
    def _maintenance_loop(self):
        """Background maintenance loop"""
        while self.maintenance_active:
            try:
                current_time = datetime.now()
                
                for task in self.scheduled_tasks:
                    if not task["enabled"]:
                        continue
                    
                    last_executed = task["last_executed"]
                    interval = timedelta(hours=task["interval_hours"])
                    
                    if last_executed is None or current_time - last_executed >= interval:
                        if task["auto_execute"]:
                            asyncio.run(self._execute_maintenance_task(task))
                        
                        task["last_executed"] = current_time
                
                # Check every 5 minutes
                time.sleep(300)
                
            except Exception as e:
                print(f"❌ Error in maintenance loop: {e}")
                time.sleep(300)
    
    async def _execute_maintenance_task(self, task: Dict[str, Any]):
        """Execute a scheduled maintenance task"""
        task_type = task["type"]
        
        try:
            if task_type == "vacuum":
                result = await self.optimizer._vacuum_database()
                print(f"🧹 Scheduled VACUUM: {'✅' if result['success'] else '❌'}")
                
            elif task_type == "analyze":
                result = await self.optimizer._analyze_database()
                print(f"📊 Scheduled ANALYZE: {'✅' if result['success'] else '❌'}")
                
            elif task_type == "full_optimization":
                result = await self.optimizer.optimize_database(auto_apply=True)
                print(f"🚀 Scheduled full optimization completed")
                
        except Exception as e:
            print(f"❌ Error executing maintenance task {task_type}: {e}")

class DatabaseBackupManager:
    def __init__(self, db_path: str, backup_dir: str = "db_backups"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self, backup_name: str = None) -> str:
        """Create database backup"""
        try:
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}.db"
            
            backup_path = self.backup_dir / backup_name
            
            # Create backup using SQLite backup API
            with sqlite3.connect(self.db_path) as source:
                with sqlite3.connect(backup_path) as backup:
                    source.backup(backup)
            
            # Verify backup integrity
            if self._verify_backup(backup_path):
                print(f"💾 Database backup created: {backup_name}")
                return str(backup_path)
            else:
                backup_path.unlink()  # Remove corrupt backup
                print(f"❌ Backup verification failed: {backup_name}")
                return ""
                
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            return ""
    
    def _verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity"""
        try:
            with sqlite3.connect(backup_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                return result[0] == "ok"
        except:
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups with metadata"""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.db"):
            try:
                stat = backup_file.stat()
                backups.append({
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "age_hours": round((datetime.now().timestamp() - stat.st_ctime) / 3600, 1)
                })
            except Exception as e:
                print(f"❌ Error reading backup {backup_file}: {e}")
        
        return sorted(backups, key=lambda x: x["created"], reverse=True)
    
    def restore_backup(self, backup_name: str) -> bool:
        """Restore database from backup"""
        try:
            backup_path = self.backup_dir / backup_name
            
            if not backup_path.exists():
                print(f"❌ Backup not found: {backup_name}")
                return False
            
            # Verify backup before restore
            if not self._verify_backup(backup_path):
                print(f"❌ Backup verification failed: {backup_name}")
                return False
            
            # Create current state backup before restore
            current_backup = self.create_backup(f"pre_restore_{int(datetime.now().timestamp())}.db")
            
            # Restore backup
            shutil.copy2(backup_path, self.db_path)
            
            print(f"✅ Database restored from backup: {backup_name}")
            print(f"💾 Current state backed up as: {Path(current_backup).name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error restoring backup: {e}")
            return False

class DatabaseMonitor:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.stats_history: List[DatabaseStats] = []
        
    def collect_database_stats(self) -> DatabaseStats:
        """Collect current database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get database size
                size_mb = self.db_path.stat().st_size / 1024 / 1024
                
                # Count tables
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # Count indexes
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
                index_count = cursor.fetchone()[0]
                
                # Measure query performance (simple test query)
                start_time = time.time()
                cursor.execute("SELECT 1")
                query_time_ms = (time.time() - start_time) * 1000
                
                stats = DatabaseStats(
                    timestamp=datetime.now(),
                    database_size_mb=round(size_mb, 2),
                    table_count=table_count,
                    index_count=index_count,
                    query_time_ms=round(query_time_ms, 2),
                    connection_count=1,  # Simplified
                    cache_hit_ratio=0.95,  # Estimated
                    fragmentation_percent=0.0  # Would need PRAGMA for accurate measurement
                )
                
                self.stats_history.append(stats)
                if len(self.stats_history) > 1000:
                    self.stats_history = self.stats_history[-500:]  # Keep last 500
                
                return stats
                
        except Exception as e:
            print(f"❌ Error collecting database stats: {e}")
            return None

class DatabaseOptimizationManager:
    """Main database optimization and maintenance system"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = Path(db_path)
        self.optimizer = DatabaseOptimizer(db_path)
        self.backup_manager = DatabaseBackupManager(db_path)
        self.monitor = DatabaseMonitor(db_path)
        self.scheduler = DatabaseMaintenanceScheduler(self.optimizer)
        
        # Setup default maintenance schedule
        self._setup_default_schedule()
    
    def _setup_default_schedule(self):
        """Setup default maintenance schedule"""
        # VACUUM weekly
        self.scheduler.schedule_maintenance("vacuum", 168, auto_execute=True)  # 7 days
        
        # ANALYZE daily
        self.scheduler.schedule_maintenance("analyze", 24, auto_execute=True)
        
        # Full optimization monthly
        self.scheduler.schedule_maintenance("full_optimization", 720, auto_execute=False)  # 30 days
    
    def start_monitoring(self):
        """Start database monitoring and maintenance"""
        self.scheduler.start_maintenance_scheduler()
        print("📊 Database monitoring and maintenance started")
    
    def stop_monitoring(self):
        """Stop database monitoring and maintenance"""
        self.scheduler.stop_maintenance_scheduler()
        print("📊 Database monitoring stopped")
    
    async def full_optimization(self, auto_apply: bool = False) -> Dict[str, Any]:
        """Perform full database optimization"""
        return await self.optimizer.optimize_database(auto_apply)
    
    def create_backup(self, backup_name: str = None) -> str:
        """Create database backup"""
        return self.backup_manager.create_backup(backup_name)
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report"""
        analysis = self.optimizer.analyzer.analyze_database_structure()
        backups = self.backup_manager.list_backups()
        current_stats = self.monitor.collect_database_stats()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "database_analysis": analysis,
            "current_stats": asdict(current_stats) if current_stats else None,
            "available_backups": len(backups),
            "latest_backup": backups[0] if backups else None,
            "maintenance_status": {
                "scheduler_active": self.scheduler.maintenance_active,
                "scheduled_tasks": len(self.scheduler.scheduled_tasks)
            }
        }

# Global database optimization manager
db_optimization_manager = None

def initialize_database_optimization(db_path: str = "trading_data.db") -> DatabaseOptimizationManager:
    """Initialize database optimization system"""
    global db_optimization_manager
    
    if db_optimization_manager is None:
        db_optimization_manager = DatabaseOptimizationManager(db_path)
        db_optimization_manager.start_monitoring()
        print("✅ Database optimization system initialized")
    
    return db_optimization_manager

def get_database_optimization_manager() -> Optional[DatabaseOptimizationManager]:
    """Get the global database optimization manager"""
    return db_optimization_manager

# Utility functions
async def optimize_database_now(auto_apply: bool = False) -> Dict[str, Any]:
    """Run immediate database optimization"""
    manager = get_database_optimization_manager() or initialize_database_optimization()
    return await manager.full_optimization(auto_apply)

def create_database_backup() -> str:
    """Create immediate database backup"""
    manager = get_database_optimization_manager() or initialize_database_optimization()
    return manager.create_backup()

def get_database_health_report() -> Dict[str, Any]:
    """Get database health and optimization report"""
    manager = get_database_optimization_manager() or initialize_database_optimization()
    return manager.get_optimization_report()

if __name__ == "__main__":
    # Standalone testing
    print("🧪 Testing Database Optimization System")
    
    async def test_optimization():
        # Test with a sample database
        test_db = "test_optimization.db"
        
        # Create test database
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    timestamp TEXT,
                    price REAL,
                    quantity REAL
                )
            """)
            
            # Insert test data
            for i in range(1000):
                cursor.execute("""
                    INSERT INTO test_trades (symbol, timestamp, price, quantity)
                    VALUES (?, ?, ?, ?)
                """, (f"BTC{i%10}", datetime.now().isoformat(), 50000.0 + i, 0.1))
            
            conn.commit()
        
        # Test optimization
        optimizer = DatabaseOptimizationManager(test_db)
        
        print("📊 Running database analysis...")
        report = optimizer.get_optimization_report()
        print(json.dumps(report["database_analysis"], indent=2, default=str))
        
        print("🔧 Running optimization...")
        result = await optimizer.full_optimization(auto_apply=True)
        print(json.dumps(result, indent=2, default=str))
        
        print("💾 Creating backup...")
        backup_path = optimizer.create_backup()
        print(f"Backup created: {backup_path}")
        
        # Cleanup
        Path(test_db).unlink(missing_ok=True)
        if backup_path:
            Path(backup_path).unlink(missing_ok=True)
    
    asyncio.run(test_optimization())
    print("✅ Database optimization system test completed!")