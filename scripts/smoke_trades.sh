#!/bin/bash
set -e

# Smoke test for trades export endpoint
# Tests the /v4/trades/export-gpt/{wallet} endpoint

# Configuration
ENDPOINT="https://web-production-2bb2f.up.railway.app"
WALLET="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
API_KEY="wd_12345678901234567890123456789012"

echo "🚀 WalletDoctor Trades Export Smoke Test"
echo "========================================"
echo "Endpoint: $ENDPOINT"
echo "Wallet: ${WALLET:0:8}..."
echo "API Key: ${API_KEY:0:10}..."
echo ""

# Test endpoint
echo "📡 Testing GET /v4/trades/export-gpt/$WALLET"
RESPONSE_FILE="/tmp/smoke_trades_response.json"

# Make the request
HTTP_CODE=$(curl -s -w "%{http_code}" \
  -H "X-Api-Key: $API_KEY" \
  -H "Accept: application/json" \
  "$ENDPOINT/v4/trades/export-gpt/$WALLET" \
  -o "$RESPONSE_FILE")

echo "HTTP Status: $HTTP_CODE"

# Check HTTP status
if [ "$HTTP_CODE" != "200" ]; then
  echo "❌ FAILED: Expected HTTP 200, got $HTTP_CODE"
  echo "Response:"
  cat "$RESPONSE_FILE"
  exit 1
fi

# Validate JSON
if ! jq . "$RESPONSE_FILE" > /dev/null 2>&1; then
  echo "❌ FAILED: Invalid JSON response"
  echo "Response:"
  cat "$RESPONSE_FILE"
  exit 1
fi

echo "✅ Valid JSON response"

# Extract key metrics
WALLET_RETURNED=$(jq -r '.wallet' "$RESPONSE_FILE")
SIGNATURES_COUNT=$(jq '.signatures | length' "$RESPONSE_FILE")
TRADES_COUNT=$(jq '.trades | length' "$RESPONSE_FILE")

# Validate structure
if [ "$WALLET_RETURNED" != "$WALLET" ]; then
  echo "❌ FAILED: Wallet mismatch. Expected: $WALLET, Got: $WALLET_RETURNED"
  exit 1
fi

if [ "$SIGNATURES_COUNT" = "null" ] || [ "$SIGNATURES_COUNT" -eq 0 ]; then
  echo "❌ FAILED: No signatures returned"
  exit 1
fi

if [ "$TRADES_COUNT" = "null" ] || [ "$TRADES_COUNT" -eq 0 ]; then
  echo "❌ FAILED: No trades returned"
  exit 1
fi

# Print metrics
echo ""
echo "📊 Results:"
echo "  Wallet: $WALLET_RETURNED"
echo "  Signatures: $SIGNATURES_COUNT"
echo "  Trades: $TRADES_COUNT"

# Validate data consistency
if [ "$TRADES_COUNT" -gt "$SIGNATURES_COUNT" ]; then
  echo "⚠️  WARNING: More trades than signatures (trades=$TRADES_COUNT, sigs=$SIGNATURES_COUNT)"
fi

# Validate trade structure (check first trade)
FIRST_TRADE=$(jq '.trades[0]' "$RESPONSE_FILE")
if [ "$FIRST_TRADE" = "null" ]; then
  echo "❌ FAILED: No trades in array"
  exit 1
fi

# Check required fields in first trade (based on actual API structure)
REQUIRED_FIELDS=("signature" "timestamp" "action" "amount" "token")
for field in "${REQUIRED_FIELDS[@]}"; do
  VALUE=$(echo "$FIRST_TRADE" | jq -r ".$field")
  if [ "$VALUE" = "null" ] || [ -z "$VALUE" ]; then
    echo "❌ FAILED: Missing required field '$field' in trade"
    exit 1
  fi
done

echo "✅ Trade structure validation passed"

# Response size check
RESPONSE_SIZE=$(stat -f%z "$RESPONSE_FILE" 2>/dev/null || stat -c%s "$RESPONSE_FILE" 2>/dev/null)
echo "  Response size: ${RESPONSE_SIZE} bytes"

if [ "$RESPONSE_SIZE" -lt 1000 ]; then
  echo "⚠️  WARNING: Response seems small ($RESPONSE_SIZE bytes)"
fi

# Performance check (rough estimate)
echo ""
echo "🔍 Sample Trade Data:"
echo "$FIRST_TRADE" | jq '{
  action: .action,
  token: .token,
  amount: .amount,
  timestamp: .timestamp,
  signature: (.signature[:8] + "...")
}'

echo ""
echo "✅ SMOKE TEST PASSED"
echo "   Endpoint is responding correctly"
echo "   JSON structure is valid"
echo "   Data contains expected signatures and trades"

# Cleanup
rm -f "$RESPONSE_FILE"

exit 0 