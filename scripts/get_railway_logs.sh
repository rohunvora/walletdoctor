#!/bin/bash
# Get Railway logs for debugging

echo "=== Getting Railway Logs ==="
echo "Note: You may need to run 'railway login' first"
echo ""

# Get recent logs
echo "Getting last 100 lines of logs..."
railway logs --tail 100 > tmp/railway_logs_$(date +%Y%m%d_%H%M%S).txt

echo "Logs saved to tmp/railway_logs_*.txt"

# Also search for specific patterns
echo ""
echo "=== Key Patterns ==="
echo ""
echo "Errors:"
railway logs --tail 200 | grep -i "error" | tail -10
echo ""
echo "Phase timings:"
railway logs --tail 200 | grep "phase=" | tail -10
echo ""
echo "Startup messages:"
railway logs --tail 200 | grep -E "(Starting|started|listening)" | tail -5 