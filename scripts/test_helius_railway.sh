#!/bin/bash
# Test Helius-only pricing on Railway deployment

echo "=== Testing Helius-Only Pricing on Railway ==="
echo "Time: $(date)"
echo ""

# 1. Check diagnostics endpoint
echo "1. Checking diagnostics..."
curl -s https://web-production-2bb2f.up.railway.app/v4/diagnostics | jq '.env.PRICE_HELIUS_ONLY' | grep -q "true"
if [ $? -eq 0 ]; then
    echo "✅ PRICE_HELIUS_ONLY is enabled"
else
    echo "❌ PRICE_HELIUS_ONLY is NOT enabled - check deployment"
    exit 1
fi
echo ""

# 2. Run timing test
echo "2. Running timing test..."
API_BASE_URL=https://web-production-2bb2f.up.railway.app \
API_KEY=wd_12345678901234567890123456789012 \
python3 scripts/test_phase_a_timing.py
echo ""

# 3. Wait a moment for logs to settle
echo "3. Waiting 5s for logs to settle..."
sleep 5

# 4. Collect logs
echo "4. Collecting [PRICE] and [RCA] logs..."
railway logs --tail 400 | grep -E '\[PRICE\]|\[RCA\]' > tmp/helius_price_logs.txt
echo "Logs saved to tmp/helius_price_logs.txt"
echo ""

# 5. Show summary
echo "5. Log summary:"
echo "Total PRICE entries: $(grep -c '\[PRICE\]' tmp/helius_price_logs.txt)"
echo "Total RCA entries: $(grep -c '\[RCA\]' tmp/helius_price_logs.txt)"
echo "Coverage entries: $(grep -c 'Coverage:' tmp/helius_price_logs.txt)"
echo ""

echo "=== Test Complete ==="
echo "Check tmp/helius_price_logs.txt for detailed logs" 