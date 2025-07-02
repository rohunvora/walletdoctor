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
Price fetching: Very slow (took over 2 minutes)
```

### Railway Production
```
Cold cache: 502 error after 32.96s
Warm cache: Connection reset after 15s
Cache warming: Timeout after 45s
```

## Root Cause Analysis

### ✅ CONFIRMED: Price Fetching is the Bottleneck
- **Birdeye API rate limit**: 1 request/second
- **Small wallet has 1074 unique trades**
- Even with batching (100 mints/call), still requires many sequential calls
- **Estimated time**: 10-15 seconds minimum for price fetching alone

### ✅ CONFIRMED: Worker Timeout Issue
- Default gunicorn timeout was 30s
- Worker gets killed before request completes
- Results in 502 errors

## Action Items

### 1. Enhanced Logging (✅ DONE)
- Added info-level phase logging to GPT export
- Will show exactly where the 30+ second delay occurs

### 2. Environment Tuning (⏳ PENDING)
**NOTE**: Railway env vars NOT updated yet per diagnostics endpoint

Need to manually update in Railway dashboard:
- `WEB_CONCURRENCY=1` (currently 2)
- `HELIUS_PARALLEL_REQUESTS=15` (currently 5)
- `HELIUS_TIMEOUT=20` (currently 15)
- `GUNICORN_TIMEOUT=60` (not set)
- `RAILWAY_PROXY_TIMEOUT=60` (not set)

### 3. Skip Pricing Debug Mode (✅ DONE)
Added `?skip_pricing=true` parameter to isolate issue:
```
/v4/positions/export-gpt/{wallet}?skip_pricing=true
```

### 4. Diagnostics Endpoint (✅ WORKING)
```
GET /v4/diagnostics
```
Shows env vars, Redis status, feature flags

## Immediate Fix

1. **Update Railway Environment Variables**:
   ```
   WEB_CONCURRENCY=1
   HELIUS_PARALLEL_REQUESTS=15
   HELIUS_TIMEOUT=20
   GUNICORN_TIMEOUT=60
   RAILWAY_PROXY_TIMEOUT=60
   LOG_LEVEL=info
   ```

2. **Test with skip_pricing**:
   ```bash
   curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
     "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya?skip_pricing=true"
   ```

3. **Monitor Phase Logs**:
   ```bash
   railway logs --tail 200 | grep "phase="
   ```

## Long-term Solutions

1. **Redis Caching** (Critical)
   - Set up Redis on Railway
   - Cache prices across requests
   - Pre-warm popular token prices

2. **Background Jobs**
   - Use Celery/RQ for heavy computations
   - Return job ID, poll for results

3. **Price Service Optimization**
   - Implement price proxy with caching
   - Use WebSocket for real-time prices
   - Consider different price provider with higher rate limits

4. **Architecture Change**
   - Consider FastAPI for true async support
   - Or use threading for price fetches in Flask

## Expected Outcome

Once env vars are updated:
- Requests should complete (even if slow)
- Phase logs will show exact bottlenecks
- skip_pricing=true should return in <5s

## Next Steps

1. **USER ACTION REQUIRED**: Update Railway env vars in dashboard
2. Wait 5 minutes for deployment
3. Test with skip_pricing=true first
4. If that works, test normal flow
5. Check phase timing logs

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