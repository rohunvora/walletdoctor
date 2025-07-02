#!/bin/bash
# Quick Railway logs without streaming/hanging

echo "=== Quick Railway Log Check ==="
echo "Getting recent logs (this won't hang)..."
echo ""

# Use timeout to get logs for just a few seconds
{
    railway logs --deployment &
    LOGS_PID=$!
    sleep 3
    kill $LOGS_PID 2>/dev/null
} > tmp/quick_logs.txt 2>&1

# Show the results
echo "Recent logs:"
tail -20 tmp/quick_logs.txt

echo ""
echo "=== Error Check ==="
grep -i "error" tmp/quick_logs.txt | tail -5

echo ""
echo "=== Boot Messages ==="
grep -E "(BOOT|Starting)" tmp/quick_logs.txt | tail -5

echo ""
echo "Full logs saved to: tmp/quick_logs.txt" 