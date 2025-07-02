# WAL-613 Railway Debugging Summary

## Issue
- Railway deployment returning 502 errors (Application failed to respond)
- Timeouts happening around 30-45 seconds
- Connection resets during requests

## Timeline
1. **Initial deployment**: Missing uvicorn caused startup failures
2. **Fixed Procfile**: Removed UvicornWorker, app starts successfully  
3. **Current state**: App starts but times out on GPT export requests

## Performance Test Results

### Local (macOS)
```
Started: 02:10:42
Signature fetch: ~1s (1677 signatures)
Transaction fetch: ~2s (1117 transactions)
Price fetching: Still running after 2+ minutes
```

### Railway Production
```
Cold cache: 502 error after 32.96s
Warm cache: Connection reset after 15s
Cache warming: Timeout after 45s
```

## Root Cause Analysis

### Hypothesis 1: Network Latency
- Railway → Helius might have higher latency than local
- Railway → Birdeye price fetching could be the bottleneck

### Hypothesis 2: Resource Constraints
- Memory limits causing worker restarts
- CPU throttling during intensive operations

### Hypothesis 3: Async/Sync Blocking
- Flask's sync nature blocking on async operations
- Gunicorn worker timeout (default 30s)

## Action Items

### 1. Enhanced Logging (DONE)
- Added info-level phase logging to GPT export
- Will show exactly where the 30+ second delay occurs

### 2. Environment Tuning
Updated Railway env vars:
- `WEB_CONCURRENCY=1` (reduce memory pressure)
- `HELIUS_PARALLEL_REQUESTS=15` (increase throughput)
- `HELIUS_TIMEOUT=20` (increase timeout)
- `GUNICORN_TIMEOUT=60` (prevent worker timeout)
- `RAILWAY_PROXY_TIMEOUT=60` (prevent proxy timeout)

### 3. Direct Testing Needed
- SSH into Railway: `railway run bash`
- Run: `./scripts/railway_shell_test.sh`
- Compare network latency vs local

### 4. Cache Warming Strategy
If Helius/Birdeye is slow on Railway:
- Implement background pre-warming
- Use Redis for cross-request caching
- Consider CDN for price data

## Next Steps

1. **Deploy env var changes** and retest
2. **Analyze Railway logs** for phase timings
3. **Run direct shell test** to isolate network issues
4. **Consider FastAPI** if sync/async is the issue

## Logs to Collect
```bash
# Get recent logs with phase timings
railway logs --tail 200 | grep -E "(phase=|ERROR|timeout)" > railway_phase_logs.txt

# Check worker restarts
railway logs --tail 500 | grep -E "(worker|restart|timeout|memory)" 
```

## ✅ Confirmed: HELIUS_KEY IS Present
Your screenshots confirm HELIUS_KEY is set in Railway, so the issue is NOT missing environment variables.

## 🔍 Debugging Tools Added

### 1. Enhanced Startup Logging
```python
# Added immediate logging on startup
logger.info("WalletDoctor GPT API Starting...")
logger.info(f"HELIUS_KEY present: {bool(os.getenv('HELIUS_KEY'))}")
```

### 2. Fixed Response Mode
Set `DEBUG_FIXED_RESPONSE=true` in Railway to bypass all async code:
```bash
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/test
```

### 3. Asyncio Fix
Updated `run_async()` to handle UvicornWorker's event loop properly.

### 4. Alternative Procfile
Created `Procfile.sync` without UvicornWorker in case that's the issue.

### 5. Minimal Test App
Created `src/api/minimal_test_app.py` to isolate framework issues.

## 📋 Next Steps for Railway Admin

1. **Add these environment variables:**
   ```
   LOG_LEVEL=debug
   DEBUG_FIXED_RESPONSE=true
   PYTHONUNBUFFERED=1
   ```

2. **Redeploy and check logs for:**
   - "WalletDoctor GPT API Starting..." message
   - Any stack traces
   - Import errors

3. **Test fixed response:**
   ```bash
   curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
     https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/test
   ```

4. **If still 502, try sync workers:**
   - Rename `Procfile.sync` to `Procfile`
   - Remove `--worker-class uvicorn.workers.UvicornWorker` from GUNICORN_CMD_ARGS

## 🎯 Most Likely Causes

1. **Asyncio/UvicornWorker Conflict** - Our Flask app uses `asyncio.run()` which conflicts with UvicornWorker
2. **Import-time Exception** - Something else failing during import (we'll see in logs)
3. **Memory Limit** - App exceeds Railway's memory during startup
4. **Network Egress** - Railway blocking calls to Helius/Birdeye

## 📁 Files Added/Modified

- `src/api/wallet_analytics_api_v4_gpt.py` - Enhanced logging, fixed asyncio, debug mode
- `Procfile.sync` - Alternative without UvicornWorker
- `src/api/minimal_test_app.py` - Minimal test to isolate issues
- `test_local_railway_env.sh` - Test locally with Railway's exact env
- `tmp/railway_debug_steps.md` - Detailed debugging guide

## Local Testing
To reproduce locally:
```bash
./test_local_railway_env.sh
# In another terminal:
curl http://localhost:8080/v4/diagnostics
```

Once we see the Railway logs with LOG_LEVEL=debug, we'll know exactly what's failing! 