"""
Alerting and Notification System (Phase 15.5)
Enterprise-grade alerting with multiple channels and intelligent routing
"""

import asyncio
import smtplib
import json
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
import sqlite3
from pathlib import Path
import time
import threading
from collections import defaultdict, deque

class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertChannel(Enum):
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    SMS = "sms"
    CONSOLE = "console"

class AlertStatus(Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

@dataclass
class AlertRule:
    name: str
    condition: str
    threshold: float
    severity: AlertSeverity
    channels: List[AlertChannel]
    cooldown_minutes: int
    auto_resolve: bool
    enabled: bool

@dataclass
class Alert:
    id: str
    rule_name: str
    title: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    status: AlertStatus
    metadata: Dict[str, Any]
    channels_sent: List[AlertChannel]
    resolution_time: Optional[datetime] = None

@dataclass
class NotificationConfig:
    email_smtp_server: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_from: str = ""
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""
    sms_api_key: str = ""
    sms_api_secret: str = ""

class AlertStorage:
    def __init__(self, db_path: str = "alerts.db"):
        self.db_path = Path(db_path)
        self._setup_database()
    
    def _setup_database(self):
        """Setup SQLite database for alert persistence"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id TEXT PRIMARY KEY,
                        rule_name TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        status TEXT NOT NULL,
                        metadata TEXT,
                        channels_sent TEXT,
                        resolution_time TEXT
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS alert_rules (
                        name TEXT PRIMARY KEY,
                        condition_expr TEXT NOT NULL,
                        threshold REAL NOT NULL,
                        severity TEXT NOT NULL,
                        channels TEXT NOT NULL,
                        cooldown_minutes INTEGER NOT NULL,
                        auto_resolve BOOLEAN NOT NULL,
                        enabled BOOLEAN NOT NULL
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            print(f"❌ Error setting up alerts database: {e}")
    
    def save_alert(self, alert: Alert):
        """Save alert to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO alerts 
                    (id, rule_name, title, message, severity, timestamp, status, 
                     metadata, channels_sent, resolution_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.id,
                    alert.rule_name,
                    alert.title,
                    alert.message,
                    alert.severity.value,
                    alert.timestamp.isoformat(),
                    alert.status.value,
                    json.dumps(alert.metadata),
                    json.dumps([c.value for c in alert.channels_sent]),
                    alert.resolution_time.isoformat() if alert.resolution_time else None
                ))
                conn.commit()
        except Exception as e:
            print(f"❌ Error saving alert: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM alerts WHERE status = 'active' ORDER BY timestamp DESC
                """)
                
                alerts = []
                for row in cursor.fetchall():
                    alert = Alert(
                        id=row[0],
                        rule_name=row[1],
                        title=row[2],
                        message=row[3],
                        severity=AlertSeverity(row[4]),
                        timestamp=datetime.fromisoformat(row[5]),
                        status=AlertStatus(row[6]),
                        metadata=json.loads(row[7]) if row[7] else {},
                        channels_sent=[AlertChannel(c) for c in json.loads(row[8])] if row[8] else [],
                        resolution_time=datetime.fromisoformat(row[9]) if row[9] else None
                    )
                    alerts.append(alert)
                
                return alerts
                
        except Exception as e:
            print(f"❌ Error getting active alerts: {e}")
            return []

class EmailNotifier:
    def __init__(self, config: NotificationConfig):
        self.config = config
    
    async def send_alert(self, alert: Alert, recipients: List[str]) -> bool:
        """Send alert via email"""
        try:
            if not EMAIL_AVAILABLE:
                print("📧 Email system not available")
                return False
                
            msg = MimeMultipart()
            msg['From'] = self.config.email_from
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            
            body = f"""
Alert Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 Alert: {alert.title}
📊 Severity: {alert.severity.value.upper()}
⏰ Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
📝 Message: {alert.message}
🔧 Rule: {alert.rule_name}

Metadata:
{json.dumps(alert.metadata, indent=2)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated alert from the Bitcoin Trading Bot monitoring system.
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port)
            server.starttls()
            server.login(self.config.email_username, self.config.email_password)
            server.sendmail(self.config.email_from, recipients, msg.as_string())
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"❌ Error sending email alert: {e}")
            return False

class SlackNotifier:
    def __init__(self, config: NotificationConfig):
        self.config = config
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to Slack"""
        try:
            severity_emoji = {
                AlertSeverity.LOW: "🟡",
                AlertSeverity.MEDIUM: "🟠", 
                AlertSeverity.HIGH: "🔴",
                AlertSeverity.CRITICAL: "💥"
            }
            
            payload = {
                "text": f"{severity_emoji.get(alert.severity, '⚠️')} Trading Bot Alert",
                "attachments": [{
                    "color": "danger" if alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL] else "warning",
                    "fields": [
                        {"title": "Alert", "value": alert.title, "short": True},
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Time", "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'), "short": True},
                        {"title": "Rule", "value": alert.rule_name, "short": True},
                        {"title": "Message", "value": alert.message, "short": False}
                    ]
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.slack_webhook_url, json=payload) as response:
                    return response.status == 200
                    
        except Exception as e:
            print(f"❌ Error sending Slack alert: {e}")
            return False

class DiscordNotifier:
    def __init__(self, config: NotificationConfig):
        self.config = config
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to Discord"""
        try:
            color_map = {
                AlertSeverity.LOW: 0xFFFF00,      # Yellow
                AlertSeverity.MEDIUM: 0xFF8000,   # Orange
                AlertSeverity.HIGH: 0xFF0000,     # Red
                AlertSeverity.CRITICAL: 0x8B0000  # Dark Red
            }
            
            embed = {
                "title": f"🤖 Trading Bot Alert",
                "description": alert.title,
                "color": color_map.get(alert.severity, 0xFF8000),
                "fields": [
                    {"name": "Severity", "value": alert.severity.value.upper(), "inline": True},
                    {"name": "Time", "value": alert.timestamp.strftime('%H:%M:%S'), "inline": True},
                    {"name": "Rule", "value": alert.rule_name, "inline": True},
                    {"name": "Message", "value": alert.message, "inline": False}
                ],
                "timestamp": alert.timestamp.isoformat()
            }
            
            payload = {"embeds": [embed]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.discord_webhook_url, json=payload) as response:
                    return response.status == 204
                    
        except Exception as e:
            print(f"❌ Error sending Discord alert: {e}")
            return False

class WebhookNotifier:
    def __init__(self, webhook_urls: List[str]):
        self.webhook_urls = webhook_urls
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to custom webhooks"""
        try:
            payload = {
                "alert_id": alert.id,
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "timestamp": alert.timestamp.isoformat(),
                "rule": alert.rule_name,
                "metadata": alert.metadata
            }
            
            success_count = 0
            async with aiohttp.ClientSession() as session:
                for url in self.webhook_urls:
                    try:
                        async with session.post(url, json=payload) as response:
                            if response.status < 400:
                                success_count += 1
                    except Exception as e:
                        print(f"❌ Error sending to webhook {url}: {e}")
            
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Error sending webhook alerts: {e}")
            return False

class AlertEvaluator:
    def __init__(self):
        self.custom_evaluators: Dict[str, Callable] = {}
        
    def register_evaluator(self, name: str, evaluator: Callable):
        """Register custom alert condition evaluator"""
        self.custom_evaluators[name] = evaluator
    
    def evaluate_condition(self, condition: str, metrics: Dict[str, Any]) -> bool:
        """Evaluate alert condition against current metrics"""
        try:
            # Replace metric references with actual values
            for key, value in metrics.items():
                condition = condition.replace(f"${key}", str(value))
            
            # Safe evaluation of mathematical expressions
            allowed_names = {
                "__builtins__": {},
                "abs": abs, "min": min, "max": max,
                "round": round, "len": len, "sum": sum,
                "True": True, "False": False
            }
            
            # Add current values
            allowed_names.update(metrics)
            
            return eval(condition, allowed_names)
            
        except Exception as e:
            print(f"❌ Error evaluating condition '{condition}': {e}")
            return False

class AlertingManager:
    """Main alerting and notification management system"""
    
    def __init__(self, config: NotificationConfig = None, db_path: str = "alerts.db"):
        self.config = config or NotificationConfig()
        self.storage = AlertStorage(db_path)
        self.evaluator = AlertEvaluator()
        
        # Initialize notifiers
        self.email_notifier = EmailNotifier(self.config)
        self.slack_notifier = SlackNotifier(self.config)
        self.discord_notifier = DiscordNotifier(self.config)
        self.webhook_notifier = WebhookNotifier([])
        
        # Alert management
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.cooldown_tracker: Dict[str, datetime] = {}
        
        # Background processing
        self.processing_active = False
        self.processing_thread = None
        
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Load default alert rules"""
        default_rules = [
            AlertRule(
                name="high_cpu_usage",
                condition="cpu_percent > 80",
                threshold=80.0,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.CONSOLE],
                cooldown_minutes=15,
                auto_resolve=True,
                enabled=True
            ),
            AlertRule(
                name="critical_memory_usage", 
                condition="memory_percent > 90",
                threshold=90.0,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.CONSOLE],
                cooldown_minutes=5,
                auto_resolve=True,
                enabled=True
            ),
            AlertRule(
                name="high_api_latency",
                condition="response_time_avg_ms > 1000",
                threshold=1000.0,
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.CONSOLE],
                cooldown_minutes=10,
                auto_resolve=True,
                enabled=True
            ),
            AlertRule(
                name="trading_api_error",
                condition="error_rate_percent > 5",
                threshold=5.0,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.CONSOLE],
                cooldown_minutes=5,
                auto_resolve=False,
                enabled=True
            ),
            AlertRule(
                name="high_trading_latency",
                condition="trading_latency_ms > 500",
                threshold=500.0,
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.CONSOLE],
                cooldown_minutes=15,
                auto_resolve=True,
                enabled=True
            ),
            AlertRule(
                name="low_trading_success_rate",
                condition="trading_success_rate < 0.7",
                threshold=0.7,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.CONSOLE],
                cooldown_minutes=30,
                auto_resolve=False,
                enabled=True
            ),
            AlertRule(
                name="high_risk_score",
                condition="risk_score > 8.0",
                threshold=8.0,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.CONSOLE],
                cooldown_minutes=5,
                auto_resolve=False,
                enabled=True
            )
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.name] = rule
    
    def add_rule(self, rule: AlertRule):
        """Add or update alert rule"""
        self.alert_rules[rule.name] = rule
        print(f"✅ Alert rule '{rule.name}' added/updated")
    
    def remove_rule(self, rule_name: str):
        """Remove alert rule"""
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]
            print(f"✅ Alert rule '{rule_name}' removed")
    
    def enable_rule(self, rule_name: str):
        """Enable alert rule"""
        if rule_name in self.alert_rules:
            self.alert_rules[rule_name].enabled = True
            print(f"✅ Alert rule '{rule_name}' enabled")
    
    def disable_rule(self, rule_name: str):
        """Disable alert rule"""
        if rule_name in self.alert_rules:
            self.alert_rules[rule_name].enabled = False
            print(f"✅ Alert rule '{rule_name}' disabled")
    
    async def evaluate_metrics(self, metrics: Dict[str, Any]):
        """Evaluate current metrics against all alert rules"""
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
                
            # Check cooldown
            if rule_name in self.cooldown_tracker:
                cooldown_end = self.cooldown_tracker[rule_name] + timedelta(minutes=rule.cooldown_minutes)
                if datetime.now() < cooldown_end:
                    continue
            
            # Evaluate condition
            if self.evaluator.evaluate_condition(rule.condition, metrics):
                await self._trigger_alert(rule, metrics)
    
    async def _trigger_alert(self, rule: AlertRule, metrics: Dict[str, Any]):
        """Trigger an alert based on rule evaluation"""
        alert_id = f"{rule.name}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            rule_name=rule.name,
            title=f"Alert: {rule.name.replace('_', ' ').title()}",
            message=f"Condition '{rule.condition}' triggered with threshold {rule.threshold}",
            severity=rule.severity,
            timestamp=datetime.now(),
            status=AlertStatus.ACTIVE,
            metadata=metrics,
            channels_sent=[]
        )
        
        # Send notifications
        await self._send_notifications(alert, rule.channels)
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        self.storage.save_alert(alert)
        
        # Set cooldown
        self.cooldown_tracker[rule.name] = datetime.now()
        
        print(f"🚨 Alert triggered: {alert.title} ({alert.severity.value})")
    
    async def _send_notifications(self, alert: Alert, channels: List[AlertChannel]):
        """Send alert through specified notification channels"""
        for channel in channels:
            try:
                success = False
                
                if channel == AlertChannel.EMAIL:
                    if self.config.email_username and self.config.email_password:
                        success = await self.email_notifier.send_alert(alert, [self.config.email_from])
                
                elif channel == AlertChannel.SLACK:
                    if self.config.slack_webhook_url:
                        success = await self.slack_notifier.send_alert(alert)
                
                elif channel == AlertChannel.DISCORD:
                    if self.config.discord_webhook_url:
                        success = await self.discord_notifier.send_alert(alert)
                
                elif channel == AlertChannel.CONSOLE:
                    self._send_console_alert(alert)
                    success = True
                
                elif channel == AlertChannel.WEBHOOK:
                    success = await self.webhook_notifier.send_alert(alert)
                
                if success:
                    alert.channels_sent.append(channel)
                    
            except Exception as e:
                print(f"❌ Error sending alert via {channel.value}: {e}")
    
    def _send_console_alert(self, alert: Alert):
        """Send alert to console output"""
        severity_icons = {
            AlertSeverity.LOW: "🟡",
            AlertSeverity.MEDIUM: "🟠",
            AlertSeverity.HIGH: "🔴", 
            AlertSeverity.CRITICAL: "💥"
        }
        
        icon = severity_icons.get(alert.severity, "⚠️")
        print(f"\n{icon} ALERT [{alert.severity.value.upper()}]: {alert.title}")
        print(f"📝 {alert.message}")
        print(f"⏰ {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 Rule: {alert.rule_name}\n")
    
    def acknowledge_alert(self, alert_id: str, acknowledger: str = "system") -> bool:
        """Acknowledge an active alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].status = AlertStatus.ACKNOWLEDGED
            self.active_alerts[alert_id].metadata["acknowledged_by"] = acknowledger
            self.active_alerts[alert_id].metadata["acknowledged_at"] = datetime.now().isoformat()
            
            self.storage.save_alert(self.active_alerts[alert_id])
            print(f"✅ Alert {alert_id} acknowledged by {acknowledger}")
            return True
        return False
    
    def resolve_alert(self, alert_id: str, resolver: str = "system") -> bool:
        """Resolve an active alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].status = AlertStatus.RESOLVED
            self.active_alerts[alert_id].resolution_time = datetime.now()
            self.active_alerts[alert_id].metadata["resolved_by"] = resolver
            
            self.storage.save_alert(self.active_alerts[alert_id])
            del self.active_alerts[alert_id]
            print(f"✅ Alert {alert_id} resolved by {resolver}")
            return True
        return False
    
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get alert summary for specified time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = [a for a in self.alert_history if a.timestamp > cutoff_time]
        
        if not recent_alerts:
            return {
                "period_hours": hours,
                "total_alerts": 0,
                "status": "quiet"
            }
        
        severity_counts = defaultdict(int)
        rule_counts = defaultdict(int)
        
        for alert in recent_alerts:
            severity_counts[alert.severity.value] += 1
            rule_counts[alert.rule_name] += 1
        
        return {
            "period_hours": hours,
            "total_alerts": len(recent_alerts),
            "active_alerts": len(self.active_alerts),
            "by_severity": dict(severity_counts),
            "by_rule": dict(rule_counts),
            "most_frequent_rule": max(rule_counts.items(), key=lambda x: x[1])[0] if rule_counts else None,
            "latest_alert": {
                "title": recent_alerts[-1].title,
                "severity": recent_alerts[-1].severity.value,
                "time": recent_alerts[-1].timestamp.isoformat()
            } if recent_alerts else None
        }
    
    def start_processing(self, check_interval: int = 60):
        """Start background alert processing"""
        if self.processing_active:
            return
            
        self.processing_active = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            args=(check_interval,),
            daemon=True
        )
        self.processing_thread.start()
        print(f"🔄 Alert processing started (interval: {check_interval}s)")
    
    def stop_processing(self):
        """Stop background alert processing"""
        self.processing_active = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        print("⏹️ Alert processing stopped")
    
    def _processing_loop(self, interval: int):
        """Background processing loop for auto-resolution and cleanup"""
        while self.processing_active:
            try:
                self._auto_resolve_alerts()
                self._cleanup_old_alerts()
                time.sleep(interval)
            except Exception as e:
                print(f"❌ Error in alert processing: {e}")
                time.sleep(interval)
    
    def _auto_resolve_alerts(self):
        """Auto-resolve alerts that have auto_resolve enabled"""
        for alert_id, alert in list(self.active_alerts.items()):
            rule = self.alert_rules.get(alert.rule_name)
            if rule and rule.auto_resolve:
                # Check if condition is no longer met (simplified)
                if datetime.now() - alert.timestamp > timedelta(minutes=30):
                    self.resolve_alert(alert_id, "auto_resolver")
    
    def _cleanup_old_alerts(self):
        """Clean up old resolved alerts from memory"""
        cutoff_time = datetime.now() - timedelta(days=7)
        self.alert_history = deque([a for a in self.alert_history if a.timestamp > cutoff_time], maxlen=1000)
    
    def export_alerts(self, format: str = "json", hours: int = 24) -> str:
        """Export alert data in specified format"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = [a for a in self.alert_history if a.timestamp > cutoff_time]
        
        if format.lower() == "json":
            return json.dumps([asdict(alert) for alert in recent_alerts], indent=2, default=str)
        elif format.lower() == "csv":
            return self._export_alerts_to_csv(recent_alerts)
        else:
            return json.dumps([asdict(alert) for alert in recent_alerts], indent=2, default=str)
    
    def _export_alerts_to_csv(self, alerts: List[Alert]) -> str:
        """Export alerts to CSV format"""
        csv_lines = ["id,rule_name,title,severity,timestamp,status,message"]
        
        for alert in alerts:
            csv_lines.append(f"{alert.id},{alert.rule_name},{alert.title},"
                           f"{alert.severity.value},{alert.timestamp.isoformat()},"
                           f"{alert.status.value},{alert.message.replace(',', ';')}")
        
        return "\n".join(csv_lines)

# Integration functions
def create_alerting_manager(email_config: Dict[str, str] = None) -> AlertingManager:
    """Create and configure alerting manager"""
    config = NotificationConfig()
    
    if email_config:
        config.email_username = email_config.get("username", "")
        config.email_password = email_config.get("password", "")
        config.email_from = email_config.get("from_email", "")
    
    manager = AlertingManager(config)
    manager.start_processing()
    
    return manager

async def process_performance_alerts(metrics: Dict[str, Any], alerting_manager: AlertingManager):
    """Process performance metrics and trigger alerts if needed"""
    await alerting_manager.evaluate_metrics(metrics)

# Global alerting manager instance
alerting_manager = None

def initialize_alerting(email_config: Dict[str, str] = None) -> AlertingManager:
    """Initialize global alerting manager"""
    global alerting_manager
    
    if alerting_manager is None:
        alerting_manager = create_alerting_manager(email_config)
        print("✅ Alerting system initialized")
    
    return alerting_manager

def get_alerting_manager() -> Optional[AlertingManager]:
    """Get the global alerting manager instance"""
    return alerting_manager

if __name__ == "__main__":
    # Standalone testing
    print("🧪 Testing Alerting and Notification System")
    
    # Create test alerting manager
    manager = AlertingManager()
    
    print("📋 Testing alert rule evaluation...")
    test_metrics = {
        "cpu_percent": 85.0,
        "memory_percent": 75.0,
        "response_time_avg_ms": 1200.0,
        "error_rate_percent": 3.0,
        "trading_latency_ms": 300.0,
        "trading_success_rate": 0.8,
        "risk_score": 6.5
    }
    
    # Test alert evaluation
    asyncio.run(manager.evaluate_metrics(test_metrics))
    
    print("📊 Alert summary:")
    summary = manager.get_alert_summary(1)
    print(json.dumps(summary, indent=2, default=str))
    
    print("✅ Alerting system test completed!")