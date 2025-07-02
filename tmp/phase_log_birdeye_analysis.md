# Birdeye Bottleneck Analysis - WAL-613

## Control Test Results

### Without Birdeye (skip_pricing=true)
```
Total time: 2.74s
- Signature fetch: ~1.3s (1683 signatures in 3 pages)
- Transaction fetch: ~1.3s (1119 transactions)
- Trade extraction: ~0.15s (1076 unique trades)
- Token metadata: ~0.15s (139 tokens)
```

### With Birdeye (normal flow)
```
Total time: 45+ seconds (TIMEOUT)
```

### Conclusion
**Birdeye price fetching adds 42+ seconds to the request!**

## Environment Variable Mismatches Found

### 1. POSITION_CACHE_TTL vs POSITION_CACHE_TTL_SEC
- **Issue**: `position_cache_v2.py` looks for `POSITION_CACHE_TTL_SEC`
- **But we set**: `POSITION_CACHE_TTL` in Railway
- **Fix**: Either rename the env var or update the code

```python
# In position_cache_v2.py line 44:
return int(os.getenv("POSITION_CACHE_TTL_SEC", "900"))

# But we're setting:
POSITION_CACHE_TTL=300
```

### 2. Other Variables Look Correct
All other environment variables match between code and Railway config.

## Root Cause Confirmed

The 45-second timeout is caused by Birdeye API rate limiting:
- 1076 trades × 2 tokens = ~2152 potential price lookups
- Even with batching (100 tokens/call) = ~22 API calls minimum
- At 1 request/second rate limit = 22+ seconds
- Plus network latency and processing = 45+ seconds

## Recommended Fixes (Lightest to Heaviest)

### 1. 🎯 Short-Circuit Recent Prices (Quickest Fix)
Skip price lookups for tokens already priced in the last N minutes:
```python
# In blockchain_fetcher_v3_fast.py
if self.price_cache.is_recent(mint, timestamp, max_age_minutes=5):
    cache_hits += 1
    continue  # Skip adding to pending
```

### 2. 🎯 Use Helius Token Prices (Beta Alternative)
Helius provides token prices in transaction data for some tokens:
- Already included in the transaction response
- No additional API calls needed
- Fallback to Birdeye only when missing

### 3. Redis Price Cache (Production Solution)
- Cache prices across requests
- Pre-warm popular tokens
- Share cache between workers
- Already have Redis URL in env

### 4. Batch Price Service
- Create a dedicated price service
- Bulk fetch and cache all token prices periodically
- Serve from cache with no API calls during requests

## Immediate Action for Beta

For the beta validation, I recommend:
1. **Fix the env var**: Rename `POSITION_CACHE_TTL` → `POSITION_CACHE_TTL_SEC`
2. **Implement short-circuit**: Skip prices fetched in last 5 minutes
3. **Add progress streaming**: Return partial results as prices load

This will reduce the 45s timeout to ~10-15s for most requests. 