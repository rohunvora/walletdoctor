# Railway Environment Variables - Phase A Fix

## Required Changes in Railway Dashboard

### 1. Rename Position Cache TTL Variable
```
OLD: POSITION_CACHE_TTL=300
NEW: POSITION_CACHE_TTL_SEC=300
```

### 2. Add Timeout Variables
```
GUNICORN_TIMEOUT=60
RAILWAY_PROXY_TIMEOUT=60
```

### 3. Update Concurrency Settings
```
WEB_CONCURRENCY=1
HELIUS_PARALLEL_REQUESTS=15
HELIUS_TIMEOUT=20
```

## Complete Environment Variable List

Copy and paste these EXACTLY into Railway dashboard:

```
HELIUS_KEY=<your key>
BIRDEYE_API_KEY=<your key>
POSITIONS_ENABLED=true
UNREALIZED_PNL_ENABLED=true
WEB_CONCURRENCY=1
HELIUS_PARALLEL_REQUESTS=15
HELIUS_TIMEOUT=20
POSITION_CACHE_TTL_SEC=300
ENABLE_CACHE_WARMING=true
FLASK_DEBUG=false
RAILWAY_PROXY_TIMEOUT=60
GUNICORN_TIMEOUT=60
LOG_LEVEL=info
```

## Testing Beta Mode

After deployment, test with these commands:

### 1. Beta Mode (Fast - No Birdeye)
```bash
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya?beta_mode=true"
```

### 2. Skip Birdeye (Alternative)
```bash
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya?skip_birdeye=true"
```

### 3. Check Environment
```bash
curl https://web-production-2bb2f.up.railway.app/v4/diagnostics
```

## Expected Results

With beta_mode=true:
- Cold cache: < 10 seconds
- Warm cache: < 0.3 seconds
- Positions returned with:
  - `current_price_usd: null`
  - `price_confidence: "unpriced"`
  - Cost basis still populated 