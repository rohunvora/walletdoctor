# Railway Deployment Error Log

## 500/502 Errors Investigation

### Date: December 2024

### Symptoms
- Small wallet (145 trades): 502 Bad Gateway
- Medium wallet (380 trades): 35s+ timeout followed by 502
- Large wallet (6,424 trades): 60s+ timeout
- Cache warming endpoint: 500 Internal Server Error

### Railway Logs
Unable to access Railway logs via CLI (not installed). Need to check Railway web dashboard.

### Local Replication Test

Testing with Railway-like environment variables:
```bash
POSITION_CACHE_TTL=300 MEMORY_GUARDRAIL_MB=512 WEB_CONCURRENCY=2 \
uvicorn src.api.wallet_analytics_api_v4_gpt:app --port 8081
```

Results:
- Health endpoint: ✅ Working (`{"status":"healthy","version":"1.1"}`)
- GPT export endpoint: ✅ Working (returns 404 with test keys as expected)
- Response time: 82.46ms (no timeout)

### Root Cause Analysis

The issue is NOT in the code itself. Local testing shows the endpoints work correctly. The Railway deployment issues are likely due to:

1. **Async Route Handler Bug (FIXED)**: The `warm_cache` endpoint was declared as `async def` which Flask doesn't support without special setup. Fixed by making it synchronous with `asyncio.run()`.

2. **Gunicorn Timeout**: The default 30s worker timeout was too short for large wallets. Fixed by adding `--timeout 120` to the Procfile.

3. **Real API Calls**: The production deployment with real Helius/Birdeye API keys may be hitting rate limits or experiencing slow responses that don't occur with test keys.

### Fix Applied

Updated `Procfile`:
```
web: gunicorn src.api.wallet_analytics_api_v4_gpt:app --timeout 120 --workers 2
```

Fixed async handler in `src/api/wallet_analytics_api_v4_gpt.py`:
```python
# Changed from:
async def warm_cache(wallet_address: str):
    cached_result = await cache.get_portfolio_snapshot(wallet_address)

# To:
def warm_cache(wallet_address: str):
    cached_result = asyncio.run(cache.get_portfolio_snapshot(wallet_address))
```

### Next Steps

1. Deploy the fixed code to Railway
2. Monitor for successful startup
3. Test cache warming endpoint
4. Measure cold vs warm cache performance 