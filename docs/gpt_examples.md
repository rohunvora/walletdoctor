# GPT Integration Examples

This document provides copy-paste examples for integrating with WalletDoctor's trades export endpoint. All examples are tested against production.

## Base Configuration

- **Base URL**: `https://web-production-2bb2f.up.railway.app`
- **Authentication**: Required via `X-Api-Key` header
- **Rate Limits**: 50 requests per minute per API key

## Example 1: Small Wallet (Success)

**Wallet**: `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`  
**Expected**: ~145 trades, ~1713 signatures  
**Response Time**: ~3-5 seconds (cold), <0.5s (warm)

### cURL Command
```bash
curl -X GET "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
  -H "X-Api-Key: wd_12345678901234567890123456789012" \
  -H "Accept: application/json"
```

### Response (200 OK)
```json
{
  "wallet": "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
  "signatures": [
    "4NyzTh42S1bGswq8BNHvsm3PxM9NBYcmYgqk1n89HjiiKWHz2sT9Ut4rmuNHjeErTBAwoQV8aYP4oM54",
    "5m5bE9B5144pJwMsv9DA4L1ovc3r6mnJSosvEc22qjc59P9KcFtHvFbMXipeCV2mzsXMrbuyyJ9FG7TC34pWPNS7",
    "3xY7QmJdLHkRqB8TzW5ez5jVRtbbYgTNijoZzp5qgkr2NHjeErTBAwoQV8aYP4oM54Ut4rmuNHji",
    "... (142 more signatures)"
  ],
  "trades": [
    {
      "action": "buy",
      "amount": 1000000.0,
      "dex": "RAYDIUM",
      "fees_usd": 0.05,
      "pnl_usd": 0.0,
      "position_closed": false,
      "price": 0.0000265,
      "priced": true,
      "signature": "4NyzTh42S1bGswq8BNHvsm3PxM9NBYcmYgqk1n89HjiiKWHz2sT9Ut4rmuNHjeErTBAwoQV8aYP4oM54",
      "timestamp": "2024-12-16T04:01:06",
      "token": "BONK",
      "token_in": {
        "amount": 1.5,
        "mint": "So11111111111111111111111111111111111111112",
        "symbol": "SOL"
      },
      "token_out": {
        "amount": 1000000.0,
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK"
      },
      "tx_type": "swap",
      "value_usd": 26.50
    },
    {
      "action": "sell",
      "amount": 500000.0,
      "dex": "RAYDIUM",
      "fees_usd": 0.05,
      "pnl_usd": 5.25,
      "position_closed": false,
      "price": 0.0000315,
      "priced": true,
      "signature": "5m5bE9B5144pJwMsv9DA4L1ovc3r6mnJSosvEc22qjc59P9KcFtHvFbMXipeCV2mzsXMrbuyyJ9FG7TC34pWPNS7",
      "timestamp": "2024-12-20T14:15:00",
      "token": "BONK",
      "token_in": {
        "amount": 500000.0,
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK"
      },
      "token_out": {
        "amount": 0.52,
        "mint": "So11111111111111111111111111111111111111112",
        "symbol": "SOL"
      },
      "tx_type": "swap",
      "value_usd": 15.75
    }
  ]
}
```

## Example 2: Authentication Error (403 Forbidden)

**Scenario**: Missing or invalid API key

### cURL Command (No API Key)
```bash
curl -X GET "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
```

### Response (403 Forbidden)
```json
{
  "error": "Authentication required",
  "message": "Please provide API key via X-Api-Key header",
  "code": "AUTH_REQUIRED"
}
```

### cURL Command (Invalid API Key)
```bash
curl -X GET "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
  -H "X-Api-Key: invalid_key_format"
```

### Response (403 Forbidden)
```json
{
  "error": "Invalid API key",
  "message": "API key must start with 'wd_' followed by 32 characters",
  "code": "INVALID_KEY_FORMAT"
}
```

## Example 3: Server Error with Retry (5xx)

**Scenario**: Service temporarily unavailable (high load or maintenance)

### Initial Request
```bash
curl -X GET "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2" \
  -H "X-Api-Key: wd_12345678901234567890123456789012"
```

### Response (502 Bad Gateway)
```json
{
  "error": "Service temporarily unavailable",
  "message": "The server is experiencing high load. Please retry.",
  "code": "SERVICE_UNAVAILABLE",
  "retry_after": 30
}
```

### Retry Script with Exponential Backoff
```bash
#!/bin/bash
# retry_with_backoff.sh

API_KEY="wd_12345678901234567890123456789012"
WALLET="3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
URL="https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/${WALLET}"

# Exponential backoff delays (seconds)
DELAYS=(1 2 4 8 16)
MAX_ATTEMPTS=5

echo "Fetching trades for wallet: ${WALLET}"

for i in $(seq 0 $((MAX_ATTEMPTS - 1))); do
  ATTEMPT=$((i + 1))
  echo -e "\nAttempt ${ATTEMPT}/${MAX_ATTEMPTS}..."
  
  # Make request and capture HTTP status
  HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
    -H "X-Api-Key: ${API_KEY}" \
    -H "Accept: application/json" \
    "${URL}")
  
  # Check response
  if [[ $HTTP_CODE -eq 200 ]]; then
    echo "✅ Success! (HTTP ${HTTP_CODE})"
    cat response.json | jq '.'
    exit 0
    
  elif [[ $HTTP_CODE -eq 429 ]]; then
    # Rate limit - check retry_after
    RETRY_AFTER=$(jq -r '.retry_after // 60' response.json)
    echo "⏳ Rate limited (HTTP ${HTTP_CODE}). Waiting ${RETRY_AFTER}s..."
    sleep $RETRY_AFTER
    
  elif [[ $HTTP_CODE -ge 500 ]] && [[ $HTTP_CODE -lt 600 ]]; then
    # Server error - use exponential backoff
    DELAY=${DELAYS[$i]:-16}  # Default to 16s if we exceed array
    echo "❌ Server error (HTTP ${HTTP_CODE}). Retrying in ${DELAY}s..."
    jq '.' response.json 2>/dev/null || cat response.json
    sleep $DELAY
    
  else
    # Other errors (4xx) - don't retry
    echo "❌ Client error (HTTP ${HTTP_CODE}). Not retrying."
    jq '.' response.json 2>/dev/null || cat response.json
    exit 1
  fi
done

echo -e "\n❌ Max attempts reached. Request failed."
exit 1
```

### Successful Retry Response (200 OK)
After retry, same structure as Example 1.

## Notes for GPT Integration

### Rate Limiting
- 50 requests/minute per API key
- 429 responses include `retry_after` field
- Implement backoff to avoid hitting limits

### Performance Expectations
- Small wallets (<500 trades): 3-5s cold, <0.5s warm
- Medium wallets (500-2000 trades): 5-10s cold, <1s warm
- Large wallets (2000+ trades): Currently limited by 30s timeout

### Error Handling Best Practices
1. Always check HTTP status before parsing JSON
2. Handle both structured errors (JSON) and raw errors (502/503)
3. Implement retry logic for 5xx errors only
4. Respect `retry_after` in rate limit responses
5. Log errors for debugging but don't expose internal details to users

### Testing Your Integration
1. Start with the small wallet example to verify connectivity
2. Test auth error handling by omitting API key
3. Test retry logic using a non-existent wallet (may trigger timeouts)
4. Monitor your rate limit usage in production

## CI Monitoring & Notifications

The WalletDoctor API includes automated daily health checks via GitHub Actions. **Slack notifications are optional** - the CI will run successfully without them.

### Optional Slack Alerts Setup

To enable Slack alerts (optional):
1. Create a Slack webhook URL in your workspace ([Slack webhook guide](https://api.slack.com/messaging/webhooks))
2. Add `SLACK_WEBHOOK_URL` secret to your GitHub repository settings
3. Format: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL`

If no webhook is configured, the CI will simply log "📋 No Slack webhook configured — skipping notification" and continue normally.

### Live Wallet Testing

The CI also performs sanity checks on live wallets to ensure data quality:
- **Small Demo**: `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya` (expected ≥500 trades)
- **Mid Demo**: `AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8` (expected ≥2000 trades)

These checks generate warnings (not failures) if trade counts are below expected levels or if wallets return errors. The sanity checks are designed to be non-blocking to ensure CI stability.

## Support

For additional examples or assistance:
- Documentation: https://walletdoctor.app/docs
- API Status: https://status.walletdoctor.app
- Support: support@walletdoctor.app 