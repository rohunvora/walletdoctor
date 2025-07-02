#!/bin/bash
# Verify Helius-only pricing is working

echo "=== Verifying Helius-Only Pricing ==="
echo ""

# 1. Check PRICE_HELIUS_ONLY is set
echo "1. Checking environment variable..."
curl -s https://web-production-2bb2f.up.railway.app/v4/diagnostics | jq -r '.env.PRICE_HELIUS_ONLY' | grep -q "true"
if [ $? -eq 0 ]; then
    echo "✅ PRICE_HELIUS_ONLY=true"
else
    echo "❌ PRICE_HELIUS_ONLY not set to true"
    exit 1
fi
echo ""

# 2. Test the endpoint with timeout
echo "2. Testing GPT export endpoint (10s timeout)..."
START=$(date +%s)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 10 \
    -H "X-Api-Key: wd_12345678901234567890123456789012" \
    "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya")
END=$(date +%s)
DURATION=$((END - START))

echo "Response: HTTP $HTTP_CODE in ${DURATION}s"
if [ "$HTTP_CODE" = "200" ] && [ $DURATION -lt 10 ]; then
    echo "✅ Success! Response in ${DURATION}s (target <8s)"
else
    echo "❌ Failed or timed out"
fi
echo ""

echo "=== Complete ==="
echo "Check logs with: railway logs --tail 50 | grep -E '\\[BOOT\\]|\\[PHASE\\]|Skipping Birdeye'" 