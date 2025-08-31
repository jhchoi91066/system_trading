"""
Performance Metrics Collection System (Phase 15.5)
Enterprise-grade performance monitoring and analytics
"""

import time
import psutil
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import json
import sqlite3
from pathlib import Path
import statistics
import sys
import traceback

@dataclass
class SystemMetrics:
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_percent: float
    network_sent_mb: float
    network_recv_mb: float
    process_count: int
    load_average: List[float]

@dataclass
class ApplicationMetrics:
    timestamp: datetime
    active_connections: int
    api_requests_per_minute: int
    response_time_avg_ms: float
    error_rate_percent: float
    database_connections: int
    cache_hit_rate: float
    queue_size: int
    memory_usage_mb: float

@dataclass
class TradingMetrics:
    timestamp: datetime
    active_positions: int
    orders_per_minute: int
    latency_ms: float
    success_rate: float
    pnl_last_hour: float
    volume_traded: float
    strategy_count: int
    risk_score: float

@dataclass
class PerformanceAlert:
    timestamp: datetime
    metric_type: str
    metric_name: str
    current_value: float
    threshold: float
    severity: str
    message: str

class MetricsCollector:
    def __init__(self):
        self.system_metrics: deque = deque(maxlen=1000)
        self.app_metrics: deque = deque(maxlen=1000)
        self.trading_metrics: deque = deque(maxlen=1000)
        self.performance_alerts: List[PerformanceAlert] = []
        self.thresholds = self._load_default_thresholds()
        self.collection_active = False
        self.collection_thread = None
        self.last_network_io = psutil.net_io_counters()
        
    def _load_default_thresholds(self) -> Dict[str, Dict[str, float]]:
        return {
            "system": {
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "disk_percent": 90.0,
                "load_average": 4.0
            },
            "application": {
                "response_time_avg_ms": 1000.0,
                "error_rate_percent": 5.0,
                "memory_usage_mb": 1024.0
            },
            "trading": {
                "latency_ms": 500.0,
                "success_rate": 0.95,
                "risk_score": 8.0
            }
        }
    
    def start_collection(self, interval: int = 30):
        """Start metrics collection in background thread"""
        if self.collection_active:
            return
            
        self.collection_active = True
        self.collection_thread = threading.Thread(
            target=self._collection_loop, 
            args=(interval,),
            daemon=True
        )
        self.collection_thread.start()
    
    def stop_collection(self):
        """Stop metrics collection"""
        self.collection_active = False
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
    
    def _collection_loop(self, interval: int):
        """Main collection loop running in background thread"""
        while self.collection_active:
            try:
                self.collect_system_metrics()
                self.collect_application_metrics()
                self.collect_trading_metrics()
                self._check_thresholds()
                time.sleep(interval)
            except Exception as e:
                print(f"❌ Error in metrics collection: {e}")
                time.sleep(interval)
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect system-level performance metrics"""
        try:
            current_network = psutil.net_io_counters()
            network_sent_mb = (current_network.bytes_sent - self.last_network_io.bytes_sent) / 1024 / 1024
            network_recv_mb = (current_network.bytes_recv - self.last_network_io.bytes_recv) / 1024 / 1024
            self.last_network_io = current_network
            
            load_avg = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
            
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=psutil.cpu_percent(interval=1),
                memory_percent=psutil.virtual_memory().percent,
                memory_used_mb=psutil.virtual_memory().used / 1024 / 1024,
                disk_percent=psutil.disk_usage('/').percent,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                process_count=len(psutil.pids()),
                load_average=load_avg
            )
            
            self.system_metrics.append(metrics)
            return metrics
            
        except Exception as e:
            print(f"❌ Error collecting system metrics: {e}")
            return None

    def collect_application_metrics(self) -> ApplicationMetrics:
        """Collect application-level performance metrics"""
        try:
            current_process = psutil.Process()
            
            metrics = ApplicationMetrics(
                timestamp=datetime.now(),
                active_connections=len(current_process.connections()),
                api_requests_per_minute=self._calculate_api_rpm(),
                response_time_avg_ms=self._calculate_avg_response_time(),
                error_rate_percent=self._calculate_error_rate(),
                database_connections=self._get_db_connections(),
                cache_hit_rate=0.95,  # Placeholder - integrate with actual cache
                queue_size=0,  # Placeholder - integrate with message queue
                memory_usage_mb=current_process.memory_info().rss / 1024 / 1024
            )
            
            self.app_metrics.append(metrics)
            return metrics
            
        except Exception as e:
            print(f"❌ Error collecting application metrics: {e}")
            return None

    def collect_trading_metrics(self) -> TradingMetrics:
        """Collect trading-specific performance metrics"""
        try:
            metrics = TradingMetrics(
                timestamp=datetime.now(),
                active_positions=self._get_active_positions(),
                orders_per_minute=self._calculate_orders_per_minute(),
                latency_ms=self._measure_api_latency(),
                success_rate=self._calculate_trading_success_rate(),
                pnl_last_hour=self._calculate_recent_pnl(),
                volume_traded=self._get_volume_traded(),
                strategy_count=self._get_active_strategy_count(),
                risk_score=self._calculate_risk_score()
            )
            
            self.trading_metrics.append(metrics)
            return metrics
            
        except Exception as e:
            print(f"❌ Error collecting trading metrics: {e}")
            return None
    
    def _calculate_api_rpm(self) -> int:
        """Calculate API requests per minute"""
        cutoff_time = datetime.now() - timedelta(minutes=1)
        recent_requests = [m for m in self.app_metrics if m.timestamp > cutoff_time]
        return len(recent_requests) * 60 // max(1, len(recent_requests))
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time from recent metrics"""
        if not self.app_metrics:
            return 0.0
        recent_times = [m.response_time_avg_ms for m in list(self.app_metrics)[-10:]]
        return statistics.mean(recent_times) if recent_times else 0.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate error rate percentage"""
        if not self.app_metrics:
            return 0.0
        recent_errors = [m.error_rate_percent for m in list(self.app_metrics)[-10:]]
        return statistics.mean(recent_errors) if recent_errors else 0.0
    
    def _get_db_connections(self) -> int:
        """Get current database connection count"""
        try:
            # Count SQLite connections (simplified)
            return len([p for p in psutil.process_iter(['connections']) 
                       if 'sqlite' in str(p.info.get('connections', []))])
        except:
            return 1
    
    def _get_active_positions(self) -> int:
        """Get count of active trading positions"""
        return 1  # Placeholder - integrate with actual position manager
    
    def _calculate_orders_per_minute(self) -> int:
        """Calculate orders executed per minute"""
        return 5  # Placeholder - integrate with order history
    
    def _measure_api_latency(self) -> float:
        """Measure API response latency"""
        return 150.0  # Placeholder - integrate with actual API monitoring
    
    def _calculate_trading_success_rate(self) -> float:
        """Calculate trading success rate"""
        return 0.75  # Placeholder - integrate with trade history
    
    def _calculate_recent_pnl(self) -> float:
        """Calculate P&L for last hour"""
        return 25.50  # Placeholder - integrate with portfolio manager
    
    def _get_volume_traded(self) -> float:
        """Get total volume traded recently"""
        return 10000.0  # Placeholder - integrate with trade history
    
    def _get_active_strategy_count(self) -> int:
        """Get count of active trading strategies"""
        return 3  # Placeholder - integrate with strategy engine
    
    def _calculate_risk_score(self) -> float:
        """Calculate current risk score (0-10 scale)"""
        return 4.5  # Placeholder - integrate with risk manager
    
    def _check_thresholds(self):
        """Check metrics against thresholds and generate alerts"""
        if not self.system_metrics or not self.app_metrics or not self.trading_metrics:
            return
            
        latest_system = self.system_metrics[-1]
        latest_app = self.app_metrics[-1]
        latest_trading = self.trading_metrics[-1]
        
        # Check system thresholds
        self._check_metric_threshold(
            "system", "cpu_percent", latest_system.cpu_percent,
            self.thresholds["system"]["cpu_percent"]
        )
        self._check_metric_threshold(
            "system", "memory_percent", latest_system.memory_percent,
            self.thresholds["system"]["memory_percent"]
        )
        
        # Check application thresholds
        self._check_metric_threshold(
            "application", "response_time_avg_ms", latest_app.response_time_avg_ms,
            self.thresholds["application"]["response_time_avg_ms"]
        )
        
        # Check trading thresholds
        self._check_metric_threshold(
            "trading", "latency_ms", latest_trading.latency_ms,
            self.thresholds["trading"]["latency_ms"]
        )
    
    def _check_metric_threshold(self, metric_type: str, metric_name: str, 
                               current_value: float, threshold: float):
        """Check individual metric against threshold"""
        if current_value > threshold:
            severity = "critical" if current_value > threshold * 1.2 else "warning"
            alert = PerformanceAlert(
                timestamp=datetime.now(),
                metric_type=metric_type,
                metric_name=metric_name,
                current_value=current_value,
                threshold=threshold,
                severity=severity,
                message=f"{metric_type.title()} {metric_name} exceeded threshold: {current_value:.2f} > {threshold:.2f}"
            )
            self.performance_alerts.append(alert)
            if len(self.performance_alerts) > 100:
                self.performance_alerts = self.performance_alerts[-50:]  # Keep last 50

class PerformanceAnalyzer:
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter metrics by time
        recent_system = [m for m in self.collector.system_metrics if m.timestamp > cutoff_time]
        recent_app = [m for m in self.collector.app_metrics if m.timestamp > cutoff_time]
        recent_trading = [m for m in self.collector.trading_metrics if m.timestamp > cutoff_time]
        
        return {
            "period_hours": hours,
            "system_summary": self._analyze_system_metrics(recent_system),
            "application_summary": self._analyze_app_metrics(recent_app),
            "trading_summary": self._analyze_trading_metrics(recent_trading),
            "alerts_summary": self._analyze_alerts(cutoff_time),
            "recommendations": self._generate_recommendations()
        }
    
    def _analyze_system_metrics(self, metrics: List[SystemMetrics]) -> Dict[str, Any]:
        """Analyze system metrics and return summary"""
        if not metrics:
            return {"status": "no_data"}
            
        cpu_values = [m.cpu_percent for m in metrics]
        memory_values = [m.memory_percent for m in metrics]
        
        return {
            "cpu": {
                "avg": statistics.mean(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values),
                "std": statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0
            },
            "memory": {
                "avg": statistics.mean(memory_values),
                "max": max(memory_values),
                "min": min(memory_values),
                "trend": "increasing" if memory_values[-1] > memory_values[0] else "stable"
            },
            "total_samples": len(metrics)
        }
    
    def _analyze_app_metrics(self, metrics: List[ApplicationMetrics]) -> Dict[str, Any]:
        """Analyze application metrics and return summary"""
        if not metrics:
            return {"status": "no_data"}
            
        response_times = [m.response_time_avg_ms for m in metrics]
        error_rates = [m.error_rate_percent for m in metrics]
        
        return {
            "response_time": {
                "avg": statistics.mean(response_times),
                "p95": sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0,
                "trend": "improving" if response_times[-1] < response_times[0] else "stable"
            },
            "error_rate": {
                "avg": statistics.mean(error_rates),
                "max": max(error_rates),
                "incidents": len([r for r in error_rates if r > 5.0])
            },
            "total_samples": len(metrics)
        }
    
    def _analyze_trading_metrics(self, metrics: List[TradingMetrics]) -> Dict[str, Any]:
        """Analyze trading metrics and return summary"""
        if not metrics:
            return {"status": "no_data"}
            
        latencies = [m.latency_ms for m in metrics]
        success_rates = [m.success_rate for m in metrics]
        pnl_values = [m.pnl_last_hour for m in metrics]
        
        return {
            "latency": {
                "avg": statistics.mean(latencies),
                "max": max(latencies),
                "p99": sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0
            },
            "performance": {
                "avg_success_rate": statistics.mean(success_rates),
                "total_pnl": sum(pnl_values),
                "profitable_periods": len([p for p in pnl_values if p > 0])
            },
            "total_samples": len(metrics)
        }
    
    def _analyze_alerts(self, cutoff_time: datetime) -> Dict[str, Any]:
        """Analyze recent alerts"""
        recent_alerts = [a for a in self.collector.performance_alerts if a.timestamp > cutoff_time]
        
        if not recent_alerts:
            return {"total_alerts": 0, "status": "healthy"}
            
        alert_counts = defaultdict(int)
        for alert in recent_alerts:
            alert_counts[alert.severity] += 1
            
        return {
            "total_alerts": len(recent_alerts),
            "by_severity": dict(alert_counts),
            "most_common": max(recent_alerts, key=lambda x: x.metric_name).metric_name if recent_alerts else None
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance improvement recommendations"""
        recommendations = []
        
        if self.collector.system_metrics:
            latest_system = self.collector.system_metrics[-1]
            if latest_system.cpu_percent > 70:
                recommendations.append("🔧 Consider CPU optimization - high CPU usage detected")
            if latest_system.memory_percent > 80:
                recommendations.append("💾 Memory optimization needed - high memory usage")
                
        if self.collector.app_metrics:
            latest_app = self.collector.app_metrics[-1]
            if latest_app.response_time_avg_ms > 500:
                recommendations.append("⚡ API response time optimization needed")
            if latest_app.error_rate_percent > 2:
                recommendations.append("🐛 Error rate is elevated - investigate logs")
                
        if not recommendations:
            recommendations.append("✅ System performance is within normal parameters")
            
        return recommendations

class PerformanceCollector:
    """Main performance collection and analysis system"""
    
    def __init__(self, db_path: str = "performance_metrics.db"):
        self.db_path = Path(db_path)
        self.collector = MetricsCollector()
        self.analyzer = PerformanceAnalyzer(self.collector)
        self._setup_database()
        
    def _setup_database(self):
        """Setup SQLite database for metrics persistence"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        cpu_percent REAL,
                        memory_percent REAL,
                        memory_used_mb REAL,
                        disk_percent REAL,
                        network_sent_mb REAL,
                        network_recv_mb REAL,
                        process_count INTEGER,
                        load_average TEXT
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS application_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        active_connections INTEGER,
                        api_requests_per_minute INTEGER,
                        response_time_avg_ms REAL,
                        error_rate_percent REAL,
                        database_connections INTEGER,
                        cache_hit_rate REAL,
                        queue_size INTEGER,
                        memory_usage_mb REAL
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trading_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        active_positions INTEGER,
                        orders_per_minute INTEGER,
                        latency_ms REAL,
                        success_rate REAL,
                        pnl_last_hour REAL,
                        volume_traded REAL,
                        strategy_count INTEGER,
                        risk_score REAL
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS performance_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        metric_type TEXT,
                        metric_name TEXT,
                        current_value REAL,
                        threshold_value REAL,
                        severity TEXT,
                        message TEXT
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            print(f"❌ Error setting up performance metrics database: {e}")
    
    def start_monitoring(self, interval: int = 30):
        """Start comprehensive performance monitoring"""
        print(f"🔍 Starting performance monitoring (interval: {interval}s)")
        self.collector.start_collection(interval)
        
    def stop_monitoring(self):
        """Stop performance monitoring"""
        print("⏹️ Stopping performance monitoring")
        self.collector.stop_collection()
        
    def save_metrics_to_db(self):
        """Save current metrics to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Save system metrics
                for metric in self.collector.system_metrics:
                    conn.execute("""
                        INSERT INTO system_metrics 
                        (timestamp, cpu_percent, memory_percent, memory_used_mb, 
                         disk_percent, network_sent_mb, network_recv_mb, 
                         process_count, load_average)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metric.timestamp.isoformat(),
                        metric.cpu_percent,
                        metric.memory_percent,
                        metric.memory_used_mb,
                        metric.disk_percent,
                        metric.network_sent_mb,
                        metric.network_recv_mb,
                        metric.process_count,
                        json.dumps(metric.load_average)
                    ))
                
                # Save application metrics
                for metric in self.collector.app_metrics:
                    conn.execute("""
                        INSERT INTO application_metrics 
                        (timestamp, active_connections, api_requests_per_minute,
                         response_time_avg_ms, error_rate_percent, database_connections,
                         cache_hit_rate, queue_size, memory_usage_mb)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metric.timestamp.isoformat(),
                        metric.active_connections,
                        metric.api_requests_per_minute,
                        metric.response_time_avg_ms,
                        metric.error_rate_percent,
                        metric.database_connections,
                        metric.cache_hit_rate,
                        metric.queue_size,
                        metric.memory_usage_mb
                    ))
                
                # Save trading metrics
                for metric in self.collector.trading_metrics:
                    conn.execute("""
                        INSERT INTO trading_metrics 
                        (timestamp, active_positions, orders_per_minute, latency_ms,
                         success_rate, pnl_last_hour, volume_traded, strategy_count, risk_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metric.timestamp.isoformat(),
                        metric.active_positions,
                        metric.orders_per_minute,
                        metric.latency_ms,
                        metric.success_rate,
                        metric.pnl_last_hour,
                        metric.volume_traded,
                        metric.strategy_count,
                        metric.risk_score
                    ))
                
                # Save alerts
                for alert in self.collector.performance_alerts:
                    conn.execute("""
                        INSERT INTO performance_alerts 
                        (timestamp, metric_type, metric_name, current_value,
                         threshold_value, severity, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        alert.timestamp.isoformat(),
                        alert.metric_type,
                        alert.metric_name,
                        alert.current_value,
                        alert.threshold,
                        alert.severity,
                        alert.message
                    ))
                
                conn.commit()
                
        except Exception as e:
            print(f"❌ Error saving metrics to database: {e}")
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        return self.analyzer.get_performance_summary(hours)
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current real-time metrics snapshot"""
        return {
            "timestamp": datetime.now().isoformat(),
            "system": asdict(self.collector.system_metrics[-1]) if self.collector.system_metrics else None,
            "application": asdict(self.collector.app_metrics[-1]) if self.collector.app_metrics else None,
            "trading": asdict(self.collector.trading_metrics[-1]) if self.collector.trading_metrics else None,
            "active_alerts": len([a for a in self.collector.performance_alerts 
                                if a.timestamp > datetime.now() - timedelta(hours=1)])
        }
    
    def export_metrics(self, format: str = "json", hours: int = 24) -> str:
        """Export metrics in specified format"""
        report = self.get_performance_report(hours)
        
        if format.lower() == "json":
            return json.dumps(report, indent=2, default=str)
        elif format.lower() == "csv":
            return self._export_to_csv(report)
        else:
            return json.dumps(report, indent=2, default=str)
    
    def _export_to_csv(self, report: Dict[str, Any]) -> str:
        """Export metrics to CSV format"""
        csv_lines = []
        csv_lines.append("metric_type,metric_name,value,timestamp")
        
        # Add system metrics
        if "system_summary" in report:
            for metric, data in report["system_summary"].items():
                if isinstance(data, dict):
                    for sub_metric, value in data.items():
                        csv_lines.append(f"system,{metric}_{sub_metric},{value},{datetime.now().isoformat()}")
        
        return "\n".join(csv_lines)

# Global performance collector instance
performance_collector = None

def initialize_performance_monitoring(db_path: str = "performance_metrics.db", 
                                    interval: int = 30) -> PerformanceCollector:
    """Initialize and start performance monitoring"""
    global performance_collector
    
    if performance_collector is None:
        performance_collector = PerformanceCollector(db_path)
        performance_collector.start_monitoring(interval)
        print(f"✅ Performance monitoring initialized (interval: {interval}s)")
    
    return performance_collector

def get_performance_collector() -> Optional[PerformanceCollector]:
    """Get the global performance collector instance"""
    return performance_collector

async def collect_and_analyze_performance() -> Dict[str, Any]:
    """Async function to collect and analyze performance"""
    if performance_collector is None:
        initialize_performance_monitoring()
    
    # Trigger immediate collection
    performance_collector.collector.collect_system_metrics()
    performance_collector.collector.collect_application_metrics()
    performance_collector.collector.collect_trading_metrics()
    
    # Save to database
    performance_collector.save_metrics_to_db()
    
    return performance_collector.get_current_metrics()

if __name__ == "__main__":
    # Standalone testing
    print("🧪 Testing Performance Metrics Collection System")
    
    collector = PerformanceCollector()
    
    print("📊 Collecting sample metrics...")
    system_metrics = collector.collector.collect_system_metrics()
    app_metrics = collector.collector.collect_application_metrics()
    trading_metrics = collector.collector.collect_trading_metrics()
    
    print(f"✅ System Metrics: CPU {system_metrics.cpu_percent}%, Memory {system_metrics.memory_percent}%")
    print(f"✅ App Metrics: Response Time {app_metrics.response_time_avg_ms}ms, Error Rate {app_metrics.error_rate_percent}%")
    print(f"✅ Trading Metrics: Latency {trading_metrics.latency_ms}ms, Success Rate {trading_metrics.success_rate*100}%")
    
    print("📈 Generating performance report...")
    report = collector.get_performance_report(1)
    print(json.dumps(report, indent=2, default=str))
    
    print("💾 Testing database save...")
    collector.save_metrics_to_db()
    print("✅ Performance metrics system test completed!")