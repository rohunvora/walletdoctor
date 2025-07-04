# Quick Start Tests - v0.8.0-prices

Verify SOL spot pricing is working by running these curl commands.

## Test 1: Small Demo Wallet Positions (18 positions)

```bash
curl -H "X-Api-Key: wd_test1234567890abcdef1234567890ab" \
  "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
  | jq '{
    schema_version,
    total_positions: .summary.total_positions,
    sample_position: .positions[0] | {
      token_symbol,
      current_price_usd,
      current_value_usd,
      price_source
    }
  }'
```

**Expected Output:**
```json
{
  "schema_version": "v0.8.0-prices",
  "total_positions": 18,
  "sample_position": {
    "token_symbol": "SOL",
    "current_price_usd": "152.64",
    "current_value_usd": "606302.79",
    "price_source": "sol_spot_price"
  }
}
```

## Test 2: Medium Demo Wallet Trades (6428 trades)

```bash
curl -H "X-Api-Key: wd_test1234567890abcdef1234567890ab" \
  "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2" \
  | jq '{
    wallet,
    total_trades: .trades | length,
    sample_trade: .trades[0] | {
      token_symbol,
      type,
      amount
    }
  }'
```

**Expected Output:**
```json
{
  "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
  "total_trades": 6428,
  "sample_trade": {
    "token_symbol": "SOL",
    "type": "buy",
    "amount": "100.5"
  }
}
```

## Validation Checklist ✅

- [ ] Both endpoints return HTTP 200
- [ ] schema_version shows "v0.8.0-prices"
- [ ] current_price_usd is non-null (should be ~$152)
- [ ] price_source shows "sol_spot_price"
- [ ] Response time <5s for positions endpoint
- [ ] At least 90% of positions have non-null pricing

## Troubleshooting

If `current_price_usd` is null:
1. Check if `PRICE_SOL_SPOT_ONLY=true` is set in production
2. Verify CoinGecko API is accessible
3. Check recent deployment logs for SOL price fetcher errors

If response time >5s:
1. First request may be cold start (retry for warm timing)
2. Medium wallet (356 positions) takes longer than small wallet
3. Check Railway deployment status 