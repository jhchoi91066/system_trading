#!/bin/bash

# Production Health Check System
# 🚀 Phase 16: Final Production Deployment

set -euo pipefail

# Configuration
HEALTH_CHECK_URL="http://localhost:8000"
WEBHOOK_URL="${WEBHOOK_URL:-}"
LOG_FILE="/Users/jinhochoi/Desktop/개발/bitcoin-trading-bot/logs/health_check.log"
ALERT_THRESHOLD=3
FAILED_CHECKS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging function
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Health check functions
check_main_application() {
    local status_code
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_CHECK_URL/health" || echo "000")
    
    if [ "$status_code" = "200" ]; then
        log "${GREEN}✅ Main application: HEALTHY${NC}"
        return 0
    else
        log "${RED}❌ Main application: UNHEALTHY (HTTP: $status_code)${NC}"
        return 1
    fi
}

check_database_connectivity() {
    local response
    response=$(curl -s "$HEALTH_CHECK_URL/api/health/database" || echo "")
    
    if echo "$response" | grep -q "\"status\":\"healthy\""; then
        log "${GREEN}✅ Database: HEALTHY${NC}"
        return 0
    else
        log "${RED}❌ Database: UNHEALTHY${NC}"
        return 1
    fi
}

check_redis_connectivity() {
    local response
    response=$(curl -s "$HEALTH_CHECK_URL/api/health/redis" || echo "")
    
    if echo "$response" | grep -q "\"status\":\"healthy\""; then
        log "${GREEN}✅ Redis: HEALTHY${NC}"
        return 0
    else
        log "${RED}❌ Redis: UNHEALTHY${NC}"
        return 1
    fi
}

check_trading_system() {
    local response
    response=$(curl -s "$HEALTH_CHECK_URL/api/trading/status" || echo "")
    
    if echo "$response" | grep -q "\"status\""; then
        log "${GREEN}✅ Trading system: HEALTHY${NC}"
        return 0
    else
        log "${RED}❌ Trading system: UNHEALTHY${NC}"
        return 1
    fi
}

check_websocket_connection() {
    # Simple WebSocket connection test using curl
    local ws_test
    ws_test=$(timeout 10s curl -s -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" "http://localhost:8000/ws/monitoring" || echo "failed")
    
    if [ "$ws_test" != "failed" ]; then
        log "${GREEN}✅ WebSocket: HEALTHY${NC}"
        return 0
    else
        log "${RED}❌ WebSocket: UNHEALTHY${NC}"
        return 1
    fi
}

check_performance_metrics() {
    local response
    response=$(curl -s "$HEALTH_CHECK_URL/api/operations/performance/current" || echo "")
    
    if echo "$response" | grep -q "cpu_percent"; then
        # Extract CPU and memory usage
        local cpu_usage=$(echo "$response" | grep -o '"cpu_percent":[0-9.]*' | cut -d: -f2)
        local memory_usage=$(echo "$response" | grep -o '"memory_percent":[0-9.]*' | cut -d: -f2)
        
        log "${GREEN}✅ Performance metrics: HEALTHY (CPU: ${cpu_usage}%, Memory: ${memory_usage}%)${NC}"
        
        # Check if resource usage is concerning
        if (( $(echo "$cpu_usage > 90" | bc -l) )); then
            log "${YELLOW}⚠️ High CPU usage: ${cpu_usage}%${NC}"
        fi
        
        if (( $(echo "$memory_usage > 90" | bc -l) )); then
            log "${YELLOW}⚠️ High memory usage: ${memory_usage}%${NC}"
        fi
        
        return 0
    else
        log "${RED}❌ Performance metrics: UNHEALTHY${NC}"
        return 1
    fi
}

# Send alert notification
send_alert() {
    local message="$1"
    local severity="$2"
    
    if [ -n "$WEBHOOK_URL" ]; then
        curl -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{
                \"text\": \"🚨 Production Alert\",
                \"attachments\": [{
                    \"color\": \"danger\",
                    \"title\": \"Health Check Failure\",
                    \"text\": \"$message\",
                    \"fields\": [
                        {\"title\": \"Severity\", \"value\": \"$severity\", \"short\": true},
                        {\"title\": \"Timestamp\", \"value\": \"$(date)\", \"short\": true},
                        {\"title\": \"Failed Checks\", \"value\": \"$FAILED_CHECKS\", \"short\": true}
                    ]
                }]
            }" >/dev/null 2>&1
    fi
}

# Main health check execution
main() {
    log "${BLUE}🏥 Starting comprehensive health check...${NC}"
    
    local checks=(
        "check_main_application"
        "check_database_connectivity" 
        "check_redis_connectivity"
        "check_trading_system"
        "check_websocket_connection"
        "check_performance_metrics"
    )
    
    local failed_checks=0
    local total_checks=${#checks[@]}
    
    for check in "${checks[@]}"; do
        if ! $check; then
            ((failed_checks++))
        fi
        sleep 1
    done
    
    # Summary
    local healthy_checks=$((total_checks - failed_checks))
    log ""
    log "${BLUE}📊 Health Check Summary:${NC}"
    log "   • Total Checks: $total_checks"
    log "   • Healthy: $healthy_checks"
    log "   • Failed: $failed_checks"
    
    if [ $failed_checks -eq 0 ]; then
        log "${GREEN}🎉 All systems are healthy!${NC}"
        exit 0
    elif [ $failed_checks -ge $ALERT_THRESHOLD ]; then
        log "${RED}🚨 CRITICAL: $failed_checks systems are unhealthy!${NC}"
        send_alert "Critical health check failure: $failed_checks/$total_checks systems are unhealthy" "critical"
        exit 1
    else
        log "${YELLOW}⚠️ WARNING: $failed_checks systems are unhealthy${NC}"
        send_alert "Health check warning: $failed_checks/$total_checks systems are unhealthy" "warning"
        exit 1
    fi
}

# Trap for cleanup
cleanup() {
    log "${BLUE}🧹 Health check completed${NC}"
}
trap cleanup EXIT

# Run main function
main "$@"