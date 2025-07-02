# Railway Phase Performance Analysis

## Test Configurations

### 1. Local Baseline (macOS)
- **Environment**: Darwin 24.5.0
- **API Keys**: Railway's production keys
- **Wallet**: 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya (small wallet)
- **Status**: Price fetching appears to be the bottleneck

### 2. Railway Production
- **Environment**: Linux container
- **Previous settings**:
  - HELIUS_PARALLEL_REQUESTS=5
  - WEB_CONCURRENCY=2
  - HELIUS_TIMEOUT=15
  - POSITION_CACHE_TTL=300
- **Updated settings** (just deployed):
  - HELIUS_PARALLEL_REQUESTS=15
  - WEB_CONCURRENCY=1
  - HELIUS_TIMEOUT=20
  - GUNICORN_TIMEOUT=60
  - RAILWAY_PROXY_TIMEOUT=60
  - LOG_LEVEL=info

## Timing Breakdown

### Local Performance
```
Time started: 02:10:42
Signature fetch: ~1s (1677 signatures in 3 pages)
Transaction fetch: ~2s (17 batches, 1117 transactions)
Price fetching: Very slow (likely the bottleneck)
```

### Railway Performance
- **Status**: Getting 502 errors (Application failed to respond)
- **Cold cache test**: Failed with 502 after 32.96s
- **Warm cache test**: Connection reset by peer after 15s
- **Cache warming**: Timed out after 45s

## Phase Logs from Railway

From latest test (02:13:23):
- Cold cache: 502 error after 32.96s
- Warm cache: Connection reset
- **Issue**: App is timing out before completing request

## Findings

1. **Local signature fetch**: Very fast (~1s for 1677 signatures)
2. **Local transaction batch**: Also fast (~2s for 1117 transactions)
3. **Price fetching**: Appears to be the major bottleneck
4. **Railway timeouts**: Worker being killed at 30s (default gunicorn timeout)

## Root Cause Analysis

### Primary Issue: Price Fetching Bottleneck
- Birdeye API rate limit: 1 request/second
- Small wallet has 1074 unique trades
- Even with batching, this requires many price lookups
- Sequential nature due to rate limit creates long delays

### Secondary Issue: Worker Timeout
- Default gunicorn timeout was 30s
- Worker gets killed before request completes
- Results in 502 errors

## Immediate Actions Taken

1. **Increased timeouts**:
   - GUNICORN_TIMEOUT=120 (in Procfile)
   - RAILWAY_PROXY_TIMEOUT=60
   
2. **Increased concurrency**:
   - HELIUS_PARALLEL_REQUESTS=15 (from 5)
   
3. **Reduced workers**:
   - WEB_CONCURRENCY=1 (from 2) to avoid memory issues

4. **Enhanced logging**:
   - LOG_LEVEL=info for phase timings

## Next Steps

1. **Wait for deployment** (~5 mins) and retest with new settings

2. **Check Railway logs** for phase timings:
   ```bash
   railway logs --tail 200 | grep "phase="
   ```

3. **If still timing out**, run direct test on Railway:
   ```bash
   railway run bash
   ./scripts/railway_shell_test.sh
   ```

4. **Long-term solutions**:
   - Implement Redis caching for prices
   - Pre-warm popular token prices
   - Consider async FastAPI instead of sync Flask
   - Use background jobs for heavy computations

## Expected Outcome

With increased timeouts, the request should complete even if slow. We'll then see exact phase timings in logs to identify which phase takes longest. 