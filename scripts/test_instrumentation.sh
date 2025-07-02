#!/bin/bash

# Test script for WAL-613 instrumentation
# This will help us identify where the 500/499 errors are coming from

API_KEY="${API_KEY:-$WALLETDOCTOR_API_KEY}"
API_URL="${API_URL:-https://walletdoctor-production.up.railway.app}"
WALLET="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"

echo "=== WAL-613 Instrumentation Test ==="
echo "Time: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "API URL: $API_URL"
echo ""

# Test 1: Diagnostics endpoint
echo "Test 1: Diagnostics endpoint"
echo "-----------------------------"
curl -s -w "\nHTTP Status: %{http_code}\nTime: %{time_total}s\n" \
     -H "X-Api-Key: $API_KEY" \
     "$API_URL/v4/diagnostics" | jq '.' || echo "Failed"

echo ""
echo "Test 2: Export GPT with beta_mode"
echo "---------------------------------"
curl -s -w "\nHTTP Status: %{http_code}\nTime: %{time_total}s\n" \
     -H "X-Api-Key: $API_KEY" \
     "$API_URL/v4/positions/export-gpt/$WALLET?beta_mode=true" | jq '.' || echo "Failed"

echo ""
echo "Test 3: Export GPT normal (may timeout)"
echo "--------------------------------------"
curl -s -w "\nHTTP Status: %{http_code}\nTime: %{time_total}s\n" \
     -m 10 \
     -H "X-Api-Key: $API_KEY" \
     "$API_URL/v4/positions/export-gpt/$WALLET" | jq '.' || echo "Failed/Timeout"

echo ""
echo "=== COMPLETE ==="
echo "Check Railway logs for:"
echo "- [BOOT] messages showing worker startup"
echo "- [REQUEST-xxx] and [PHASE-xxx] messages"
echo "- Error stack traces with request IDs" 