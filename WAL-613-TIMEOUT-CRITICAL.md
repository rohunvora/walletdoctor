# WAL-613 CRITICAL: 45+ Second Timeouts

## Current Status
- **Health endpoint**: ✅ Works fine
- **Diagnostics endpoint**: ✅ Works fine  
- **GPT Export endpoint**: ❌ Times out after 45+ seconds
- **Warm Cache endpoint**: ❌ Also times out

## Root Cause Analysis

The app starts but hangs when processing wallet data. Likely causes:

1. **Helius API Latency**
   - Fetching 145 trades with only 5 parallel requests
   - Each batch might take several seconds

2. **Async/Sync Deadlock**
   - Flask with sync gunicorn workers + `asyncio.run()` in threads
   - Can cause thread pool exhaustion

3. **Missing Redis Cache**
   - No cache = every request is cold
   - Redis connection refused (expected on Railway)

## Immediate Actions for Railway Admin

### 1. Update Environment Variables
```
HELIUS_PARALLEL_REQUESTS=15
HELIUS_TIMEOUT=30
HELIUS_MAX_RETRIES=1
PYTHONUNBUFFERED=1
WEB_CONCURRENCY=1
```

### 2. Check Railway Logs
Look for:
- "phase=helius_fetch took=XXs" 
- Memory usage graphs
- Any Python tracebacks

### 3. Test Diagnostics First
```bash
# This should show the updated env vars
curl https://web-production-2bb2f.up.railway.app/v4/diagnostics
```

## Performance Target vs Reality

- **Target**: < 30s cold cache
- **Current**: > 45s timeout
- **Gap**: Need 15+ second improvement

## If Still Timing Out

### Option 1: Quick Win - Reduce Wallet Size
Test with a tiny wallet first:
```bash
# Empty wallet - should return immediately
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/EmptyWalletAddressHere
```

### Option 2: Add Streaming Response
Modify the endpoint to stream partial results instead of waiting for everything.

### Option 3: Background Processing
Return a job ID immediately, process in background, poll for results.

## Optimization Priority

1. **Increase `HELIUS_PARALLEL_REQUESTS`** (quickest fix)
2. **Add Redis** for caching (medium effort)
3. **Refactor to pure async** (larger effort)

The app is functional but needs performance tuning for production use! 