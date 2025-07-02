# WAL-613 Phase A Complete - Beta Mode Ready

## What I've Implemented

### 1. Beta Mode Feature
Added three ways to skip Birdeye pricing:
- `?beta_mode=true` 
- `?skip_birdeye=true`
- `?skip_pricing=true`

All three parameters disable Birdeye API calls and return positions without current prices.

### 2. Null Price Handling
When pricing is skipped:
- `current_price_usd: null`
- `current_value_usd: null`
- `unrealized_pnl_usd: null`
- `unrealized_pnl_pct: null`
- `price_confidence: "unpriced"`
- Cost basis and position data still populated

### 3. Code Changes
- **API Layer**: Added beta_mode parameter handling
- **Schema Formatter**: Handle null prices gracefully
- **PnL Calculator**: Skip price fetching when requested
- **Logging**: Added skip_pricing status to logs

## Your Action Items

### 1. Update Railway Environment Variables

In Railway dashboard, make these changes:

```bash
# RENAME THIS ONE:
POSITION_CACHE_TTL_SEC=300  # was POSITION_CACHE_TTL

# ADD THESE:
GUNICORN_TIMEOUT=60
RAILWAY_PROXY_TIMEOUT=60

# UPDATE THESE:
WEB_CONCURRENCY=1           # was 2
HELIUS_PARALLEL_REQUESTS=15 # was 5
HELIUS_TIMEOUT=20           # was 15
LOG_LEVEL=info              # was debug
```

See `railway-env-fix-phase-a.md` for the complete list.

### 2. Wait for Deployment (~5 minutes)

### 3. Run Timing Test

```bash
python3 scripts/test_phase_a_timing.py
```

This will:
- Test cold cache response time (target < 10s)
- Test warm cache response time (target < 0.3s)
- Verify environment variables
- Save results to `tmp/phase_a_timing_*.json`

## Expected Results

### Cold Cache (first request)
- Helius fetch: ~3s
- Position building: ~1s
- Total: **< 10 seconds** ✅

### Warm Cache (subsequent requests)
- Cache hit
- Total: **< 0.3 seconds** ✅

### Response Format
```json
{
  "schema_version": "1.1",
  "wallet": "34zYDgjy...",
  "positions": [{
    "token_symbol": "USDC",
    "balance": "1000.0",
    "cost_basis_usd": "1000.0",
    "current_price_usd": null,
    "current_value_usd": null,
    "unrealized_pnl_usd": null,
    "price_confidence": "unpriced",
    ...
  }]
}
```

## Manual Test Commands

```bash
# Test beta mode
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya?beta_mode=true"

# Check environment
curl https://web-production-2bb2f.up.railway.app/v4/diagnostics
```

## Phase B Preview

Tomorrow we'll implement:
1. **Helius price extraction** - Use prices from DEX swaps
2. **Redis cache setup** - Share prices across requests
3. **Smart price reuse** - 5-minute window caching

But for now, Phase A gets beta unblocked with sub-10s responses! 