#!/bin/bash
# Quick test for Helius-only pricing after env vars are set

echo "=== Quick Helius-Only Test ==="
echo ""

# 1. Check env vars
echo "1. Environment check:"
ENV_DATA=$(curl -s https://web-production-2bb2f.up.railway.app/v4/diagnostics | jq '.env')
echo "$ENV_DATA" | jq '{PRICE_HELIUS_ONLY, POSITION_CACHE_TTL_SEC}'
echo ""

# 2. Quick timing test
echo "2. Timing test (10s timeout):"
time curl -s -f -m 10 \
    -H "X-Api-Key: wd_12345678901234567890123456789012" \
    "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
    -o /dev/null \
    && echo "✅ Success!" \
    || echo "❌ Failed or timed out"
echo ""

# 3. Check for key log message
echo "3. Key log to look for:"
echo 'railway logs --tail 100 | grep "Skipping Birdeye"'
echo ""

echo "If you see 'Skipping Birdeye - using Helius-only pricing' in logs, it's working!" 