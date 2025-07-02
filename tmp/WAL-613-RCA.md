# WAL-613 Blameless Root Cause Analysis

## Problem Statement
GPT export endpoint times out after 45 seconds on Railway deployment, resulting in 502 errors.

## Current Evidence
1. **Signature fetch**: ~1s (1677 signatures)
2. **Transaction fetch**: ~2s (1117 transactions) 
3. **Total timeout**: 45s (hard limit)
4. **Local test**: Still running after 2+ minutes
5. **Small wallet**: 1074 unique trades

## Hypothesis Brainstorm

### H1: Birdeye Rate Limit Bottleneck
- Birdeye allows 1 request/second
- Even with batching (100 tokens/request), need ~11 requests minimum
- Sequential due to rate limit = 11+ seconds just for price API calls
- **Likelihood: HIGH** - Math supports this

### H2: Price Lookup Algorithm Inefficiency
- Possible N² complexity in price matching logic
- Maybe checking every trade against every price point
- Could be building unnecessary price ladders
- **Likelihood: MEDIUM** - Code review needed

### H3: Network Egress from Railway
- Railway → Birdeye might have high latency
- Railway → Helius could be throttled
- Regional distance between services
- **Likelihood: MEDIUM** - Railway in US, APIs likely US too

### H4: Async/Sync Deadlock
- Flask running sync code that calls async functions
- Event loop conflicts with run_async wrapper
- Thread pool exhaustion
- **Likelihood: LOW** - Would fail consistently, not just timeout

### H5: Memory/GC Pressure
- Large data structures causing GC pauses
- Railway container memory limits
- Python object overhead with 1000+ trades
- **Likelihood: LOW** - Would see OOM errors

### H6: JSON Serialization Overhead
- Converting Decimal objects to strings
- Large response payload construction
- Multiple serialization passes
- **Likelihood: LOW** - Usually milliseconds, not seconds

### H7: Hidden Retry Loops
- Failed price lookups being retried
- Network timeouts triggering retries
- Exponential backoff accumulating
- **Likelihood: MEDIUM** - Common in API clients

## Top 2 Most Plausible Causes

### 🎯 Primary Suspect: H1 - Birdeye Rate Limit
**Evidence:**
- 1074 unique trades requiring price lookups
- 1 req/sec rate limit = minimum 11 seconds
- Actual implementation might be less efficient
- Local test taking 2+ minutes aligns with this

### 🎯 Secondary Suspect: H7 - Hidden Retry Loops
**Evidence:**
- No timeout errors, just long delays
- Could be retrying failed price lookups
- Default retry counts could multiply delays

## Validation Plan

### Phase 1: Enhanced Price Fetch Logging
Add these specific logs to isolate the bottleneck:

```python
# In UnrealizedPnLCalculator.create_position_pnl_list
logger.info(f"Starting price fetch for {len(positions)} positions")
logger.info(f"Unique tokens to price: {len(unique_tokens)}")

# In price fetch loop
logger.info(f"Fetching batch {batch_num}/{total_batches} ({len(tokens)} tokens)")
logger.info(f"Birdeye request {i}: {elapsed:.2f}s")

# After each Birdeye call
logger.info(f"Birdeye response: {status_code}, tokens priced: {success_count}/{requested}")
```

### Phase 2: Retry Detection
```python
# In Birdeye client
logger.info(f"Birdeye retry {attempt}/{max_retries} after {retry_delay}s")
```

### Phase 3: Skip Pricing Test
Already implemented with `?skip_pricing=true` - this will confirm if prices are the issue.

## Validation Instrumentation Added

### UnrealizedPnLCalculator
```python
logger.info(f"[RCA] Starting price fetch for {len(positions)} positions")
logger.info(f"[RCA] Unique tokens to price: {len(unique_tokens)}")
logger.info(f"[RCA] Price fetch completed in {elapsed:.2f}s")
```

### BlockchainFetcherV3Fast
```python
# Price batch creation
logger.info(f"[RCA] Unique mints: {len(unique_mints)}, Cache hits: {cache_hits}, Cache misses: {cache_misses}")
logger.info(f"[RCA] Created {len(batches)} Birdeye batches for {cache_misses} missing prices")

# Batch group timing
logger.info(f"[RCA] Batch group {i//3 + 1}: {len(batch_group)} batches in {group_elapsed:.2f}s")

# Individual batch details
logger.info(f"[RCA] Batch {batch_num}: Rate limit delay {acquire_time:.2f}s")
logger.info(f"[RCA] Batch {batch_num}: Requesting prices for {len(mints)} tokens")
logger.info(f"[RCA] Batch {batch_num}: Response status={resp.status} in {elapsed:.2f}s")
logger.info(f"[RCA] Batch {batch_num}: Priced {success_count}/{len(mints)} tokens")
```

## Execution Plan

1. **Deploy** (commit pushed)
2. **Run test script**: `python3 scripts/test_rca_validation.py`
3. **Collect logs**: `railway logs --tail 500 | grep '[RCA]' > tmp/phase_log_TIMESTAMP.txt`
4. **Analyze results**

## Expected Log Pattern

If H1 (Birdeye rate limit) is correct:
```
[RCA] Unique mints: ~500-1000
[RCA] Created 11+ Birdeye batches
[RCA] Batch 1: Rate limit delay 0.00s  (first is immediate)
[RCA] Batch 2: Rate limit delay 1.00s  (subsequent wait for rate limit)
[RCA] Batch 3: Rate limit delay 1.00s
...
[RCA] All 11 Birdeye batches completed in 30-45s
```

If H7 (Hidden retries) is correct:
```
[RCA] Batch X: Response status=429
[RCA] Batch X: Rate limited! Retry-After: Y
[RCA] Batch X: Error after Zs: <retry error>
``` 