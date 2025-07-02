# Railway Phase Performance Analysis

## Test Configurations

### 1. Local Baseline (macOS)
- **Environment**: Darwin 24.5.0
- **API Keys**: Railway's production keys
- **Wallet**: 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya (small wallet)
- **Status**: Running...

### 2. Railway Production
- **Environment**: Linux container
- **Current settings**:
  - HELIUS_PARALLEL_REQUESTS=5
  - WEB_CONCURRENCY=2
  - HELIUS_TIMEOUT=15
  - POSITION_CACHE_TTL=300

## Timing Breakdown

### Local Performance
```
Time started: 02:10:42
Signature fetch: ~1s (1677 signatures in 3 pages)
Transaction fetch: ~2s (17 batches)
Still running... (fetching prices)
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
- **Issue**: App is crashing or timing out before sending response

## Findings

1. **Local signature fetch**: Very fast (~1s for 1677 signatures)
2. **Local transaction batch**: Also fast (~2s for 1117 transactions)
3. **Price fetching**: Appears to be the bottleneck (still running locally)

## Next Steps

1. Deploy enhanced logging to Railway
2. Run blockchain fetcher directly on Railway shell
3. Compare network latency between local and Railway
4. Test with increased concurrency settings 