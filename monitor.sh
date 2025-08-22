#!/bin/bash

# Bitcoin Trading Bot Monitoring Script
# This script monitors the PM2 process and API health

LOG_FILE="./logs/monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting monitoring check..." >> $LOG_FILE

# Check PM2 process status
PM2_STATUS=$(pm2 jlist | jq '.[] | select(.name=="bitcoin-trading-bot") | .pm2_env.status' 2>/dev/null)

if [ "$PM2_STATUS" = '"online"' ]; then
    echo "[$DATE] ✅ PM2 process: ONLINE" >> $LOG_FILE
else
    echo "[$DATE] ❌ PM2 process: OFFLINE - Attempting restart..." >> $LOG_FILE
    pm2 restart bitcoin-trading-bot >> $LOG_FILE 2>&1
fi

# Check API health
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)

if [ "$HTTP_STATUS" = "200" ]; then
    echo "[$DATE] ✅ API health: OK" >> $LOG_FILE
else
    echo "[$DATE] ❌ API health: FAILED (HTTP $HTTP_STATUS)" >> $LOG_FILE
fi

# Check memory usage
MEMORY_USAGE=$(pm2 jlist | jq '.[] | select(.name=="bitcoin-trading-bot") | .monit.memory' 2>/dev/null)
echo "[$DATE] 📊 Memory usage: $MEMORY_USAGE bytes" >> $LOG_FILE

# Check active strategies
ACTIVE_STRATEGIES=$(ls -la ./backend/data/active_strategies.json 2>/dev/null | wc -l)
echo "[$DATE] 📈 Active strategies file exists: $ACTIVE_STRATEGIES" >> $LOG_FILE

echo "[$DATE] Monitoring check completed." >> $LOG_FILE
echo "" >> $LOG_FILE