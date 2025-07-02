#!/bin/bash
# Get Railway logs for debugging

echo "=== Getting Railway Logs ==="
echo "Note: You may need to run 'railway login' first"
echo ""

# Get recent logs
echo "Getting deployment logs..."
railway logs > tmp/railway_logs_$(date +%Y%m%d_%H%M%S).txt &
LOGS_PID=$!
sleep 5  # Let it collect some logs
kill $LOGS_PID 2>/dev/null || true

echo "Logs saved to tmp/railway_logs_*.txt"

# Also search for specific patterns using recent log file
LATEST_LOG=$(ls -t tmp/railway_logs_*.txt 2>/dev/null | head -1)
if [ -f "$LATEST_LOG" ]; then
    echo ""
    echo "=== Key Patterns ==="
    echo ""
    echo "Errors:"
    grep -i "error" "$LATEST_LOG" | tail -10
    echo ""
    echo "Phase timings:"
    grep "phase=" "$LATEST_LOG" | tail -10
    echo ""
    echo "Startup messages:"
    grep -E "(Starting|started|listening)" "$LATEST_LOG" | tail -5
else
    echo "Use 'railway logs' for real-time log streaming"
fi 