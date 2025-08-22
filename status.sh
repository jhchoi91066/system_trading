#!/bin/bash

# Bitcoin Trading Bot Status Dashboard
clear

echo "🚀 Bitcoin Trading Bot - 24/7 Status Dashboard"
echo "==============================================="
echo ""

echo "📊 PM2 Process Status:"
pm2 status

echo ""
echo "🔗 API Health Check:"
API_RESPONSE=$(curl -s http://localhost:8000/)
if [ $? -eq 0 ]; then
    echo "✅ API is responding: $API_RESPONSE"
else
    echo "❌ API is not responding"
fi

echo ""
echo "📈 Active Strategies:"
if [ -f "./backend/data/active_strategies.json" ]; then
    ACTIVE_COUNT=$(grep '"is_active": true' ./backend/data/active_strategies.json | wc -l)
    echo "✅ Active strategies: $ACTIVE_COUNT"
    echo "📄 Strategy file exists and contains data"
else
    echo "❌ No active strategies file found"
fi

echo ""
echo "📝 Recent Logs (last 5 lines):"
if [ -f "./logs/combined.log" ]; then
    tail -5 ./logs/combined.log
else
    echo "No logs available yet"
fi

echo ""
echo "💾 System Resources:"
echo "Memory usage: $(pm2 jlist | jq '.[] | select(.name=="bitcoin-trading-bot") | .monit.memory' 2>/dev/null || echo 'N/A') bytes"
echo "CPU usage: $(pm2 jlist | jq '.[] | select(.name=="bitcoin-trading-bot") | .monit.cpu' 2>/dev/null || echo 'N/A')%"

echo ""
echo "🕒 Last Updated: $(date)"
echo "==============================================="