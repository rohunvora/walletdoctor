# Helius Paid Plan Update

**Date**: Dec 20, 2024
**Status**: Configured but still hitting rate limits

## Configuration Changes

Updated `src/lib/blockchain_fetcher_v3.py` for 50 RPS paid plan:
- `HELIUS_RPS`: 10 → 50
- `max_concurrent`: 10 → 40 (leaving buffer)
- `parallel_pages`: 15 → 40 (default)

## Test Results

With the large wallet (5,478 trades, 86 pages):
- **Initial performance**: Much faster page fetching
- **Rate limits hit**: Still getting 429 errors around batch 10-14
- **Pattern**: Suggests burst rate limiting even with paid plan

## Observations

1. **Faster initial processing**: Pages fetched much quicker initially
2. **Rate limit behavior**: Still hitting 429s with batch retries
3. **Possible causes**:
   - API key might not be on paid plan yet
   - Paid plan may have burst limits (e.g., 50 RPS sustained but lower burst)
   - Need to verify API key status with Helius

## Current Performance

Even with rate limits, the increased concurrency should provide:
- Better throughput between rate limit hits
- Faster recovery with batch-wide retry logic
- More efficient use of available rate limit

## Recommendations

1. **Verify API key**: Confirm the API key is actually on the paid plan
2. **Adjust concurrency**: Maybe reduce to 30-35 concurrent requests
3. **Monitor pattern**: Track when rate limits occur to understand burst behavior
4. **Contact support**: If on paid plan, ask Helius about burst limits

## Code Status

The code is configured for 50 RPS and will automatically benefit when:
- API key is confirmed on paid plan
- Any burst limit issues are resolved
- No code changes needed once rate limits are sorted 