# Railway Environment Variables - Helius-Only Pricing Update

## New Variable to Add

```bash
# Enable Helius-only pricing (bypass Birdeye completely)
PRICE_HELIUS_ONLY=true
```

## Complete Environment for WAL-613 Helius-Only Mode

```bash
# API Keys (existing)
HELIUS_KEY=<your_key>
BIRDEYE_API_KEY=<your_key>  # Still needed for other endpoints

# Redis (existing)
REDIS_URL=<your_redis_url>

# Feature Flags
POSITIONS_ENABLED=true
UNREALIZED_PNL_ENABLED=true
PRICE_HELIUS_ONLY=true  # NEW - Enable Helius-only pricing

# Performance Settings
WEB_CONCURRENCY=1
HELIUS_PARALLEL_REQUESTS=15
HELIUS_TIMEOUT=20
POSITION_CACHE_TTL_SEC=300  # Fixed from POSITION_CACHE_TTL
GUNICORN_TIMEOUT=60
RAILWAY_PROXY_TIMEOUT=60

# Logging
LOG_LEVEL=info

# Cost Basis
COST_BASIS_METHOD=fifo
```

## Deployment Steps

1. Add `PRICE_HELIUS_ONLY=true` to Railway environment
2. Rename `POSITION_CACHE_TTL` to `POSITION_CACHE_TTL_SEC` if not already done
3. Redeploy the service
4. Monitor logs for `[PRICE]` entries to see coverage

## Expected Behavior

With `PRICE_HELIUS_ONLY=true`:
- Birdeye API will NOT be called for pricing
- Prices extracted from DEX swap transactions in Helius data
- Tokens without recent swaps will have null prices
- Target performance: <8s cold, <0.5s warm

## Monitoring

Look for these log entries:
- `[PRICE] Using Helius-only pricing for <token>`
- `[PRICE] Coverage: X/Y from swaps, Z/Y from cache`
- `[PRICE] Helius price extraction completed in X.XXs` 