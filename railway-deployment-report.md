# Railway Deployment Report - WAL-613

## Environment Variables

Set these in Railway dashboard (Settings → Variables):

```bash
# Performance optimizations
WEB_CONCURRENCY=2
GUNICORN_CMD_ARGS=--timeout 120 --worker-class uvicorn.workers.UvicornWorker
HELIUS_PARALLEL_REQUESTS=5
HELIUS_MAX_RETRIES=2
HELIUS_TIMEOUT=15
POSITION_CACHE_TTL=300
ENABLE_CACHE_WARMING=true
PYTHONUNBUFFERED=1

# API Keys (keep existing values)
HELIUS_API_KEY=<your_key>
BIRDEYE_API_KEY=<your_key>
```

**Important**: Enter values WITHOUT quotes in Railway UI

## Deployment Configuration

**Procfile updated**:
```
web: gunicorn src.api.wallet_analytics_api_v4_gpt:app --workers $WEB_CONCURRENCY --timeout 120 --worker-class uvicorn.workers.UvicornWorker --bind "0.0.0.0:$PORT"
```

Key changes:
- Uses `$WEB_CONCURRENCY` for dynamic worker count
- Added `uvicorn.workers.UvicornWorker` for async compatibility
- Explicit bind to `0.0.0.0:$PORT`

## Performance Test Command

After deployment, run:
```bash
API_BASE_URL=https://walletdoctor.app API_KEY=<your_key> python3 scripts/test_railway_performance.py
```

## Expected Timing Results

### Target Performance
- **Cold Cache**: < 30s ✅
- **Warm Cache**: < 0.2s ✅

### Timing Breakdown Template
```json
{
  "timestamp": "2024-XX-XX",
  "base_url": "https://walletdoctor.app",
  "wallet": "34zYDgjy9Uyj9NZnDVKBB45urkbBV4h5LzxWjXJg9VCya",
  "results": [
    {
      "test_name": "Cold Cache",
      "total_time": "XX.XXs",
      "server_time": "XX.XXs",
      "network_time": "XX.XXs",
      "cache_status": "MISS",
      "breakdown": {
        "helius_fetch": "XX.XXs",
        "position_calc": "XX.XXs", 
        "price_lookup": "XX.XXs",
        "serialization": "XX.XXs"
      }
    },
    {
      "test_name": "Warm Cache",
      "total_time": "XX.XXs",
      "server_time": "XX.XXs",
      "network_time": "XX.XXs",
      "cache_status": "HIT"
    }
  ]
}
```

## Next Steps

If cold cache > 30s after optimizations:
1. Check breakdown to identify bottleneck
2. Consider background processing approach
3. Implement progress token system 