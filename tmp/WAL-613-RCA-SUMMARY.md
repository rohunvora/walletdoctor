# WAL-613 RCA Summary - Ready for Validation

## Hypothesis Ranking (7 identified, 2 prioritized)

### 🎯 H1: Birdeye Rate Limit (PRIMARY)
- **Evidence**: 1074 trades × 2 tokens = ~2000 price lookups
- **Math**: Even with 100-token batches → 20+ Birdeye calls at 1 req/sec = 20+ seconds minimum
- **Likelihood**: HIGH

### 🎯 H7: Hidden Retry Loops (SECONDARY)  
- **Evidence**: No explicit errors, just timeouts
- **Theory**: Failed price lookups being retried with exponential backoff
- **Likelihood**: MEDIUM

### Other Hypotheses (deprioritized)
- H2: Price algorithm O(n²) complexity - MEDIUM
- H3: Railway network latency - MEDIUM  
- H4: Async/sync deadlock - LOW
- H5: Memory/GC pressure - LOW
- H6: JSON serialization - LOW

## Validation Instrumentation Deployed

Added `[RCA]` tagged logging to track:
1. **Total unique tokens** to price
2. **Cache hit/miss ratio**
3. **Number of Birdeye batches** created
4. **Time per batch** including rate limit delays
5. **Success rate** per batch
6. **Any retry behavior**

## Next Steps (Your Action Required)

### 0. Update Railway Environment Variables (CRITICAL)
The diagnostics endpoint showed these are NOT updated yet:
```
WEB_CONCURRENCY=1         (currently 2)
HELIUS_PARALLEL_REQUESTS=15  (currently 5)  
HELIUS_TIMEOUT=20         (currently 15)
GUNICORN_TIMEOUT=60       (not set)
RAILWAY_PROXY_TIMEOUT=60  (not set)
```
Update these in Railway dashboard first!

### 1. Wait for Deployment (~5 minutes)
The RCA logging code has been pushed to main.

### 2. Run Single Test
```bash
python3 scripts/test_rca_validation.py
```

This will:
- Test with `skip_pricing=true` first (baseline)
- Test normal flow with full pricing
- Save results to `tmp/rca_response_TIMESTAMP.json`

### 3. Collect Railway Logs
```bash
railway logs --tail 500 | grep '\[RCA\]' > tmp/phase_log_$(date +%Y%m%d_%H%M%S).txt
```

Or manually from Railway dashboard, search for "[RCA]" lines.

### 4. Share the Results
Paste the phase log content so we can see:
- Exact number of Birdeye batches
- Time between batches (rate limit delay)
- Total price fetch duration
- Any errors or retries

## Expected Validation Results

If **H1 is correct** (Birdeye rate limit):
```
[RCA] Created 20+ Birdeye batches for 2000+ missing prices
[RCA] Batch 1: Rate limit delay 0.00s
[RCA] Batch 2: Rate limit delay 1.00s  ← Rate limited
[RCA] All 20 Birdeye batches completed in 20-40s
```

If **H7 is correct** (Hidden retries):
```
[RCA] Batch X: Response status=429
[RCA] Batch X: Rate limited! Retry-After: 60
[RCA] Batch X: Error after 30s: timeout
```

## Why This Matters

Once we confirm which hypothesis is correct, we can implement the right fix:
- **H1 → Redis caching** + batch pre-warming
- **H7 → Disable retries** + fail fast

No more blind iterations! 