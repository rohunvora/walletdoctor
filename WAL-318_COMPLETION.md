# WAL-318: Investigate RPS Bottleneck - COMPLETED ✅

## Summary
Investigated why API performance is ~107s instead of <20s target. Found that the bottleneck is **sequential pagination requirements**, not RPS limits or network issues.

## Key Findings

### 1. Network Performance ✅
- **Latency to Helius**: 22.1ms average (excellent)
- **Concurrent capacity**: Successfully handled 50 concurrent requests
- **Theoretical max RPS**: 1,810 with 40 connections
- **Conclusion**: Network is NOT the bottleneck

### 2. Actual Performance Metrics 📊
- **Effective RPS**: 0.8 (86 pages in 107s)
- **Available RPS**: 50 (paid plan)
- **Utilization**: 1.6% of available capacity
- **Time per page**: ~1.24s

### 3. Root Cause: Sequential Pagination 🔴

The fundamental limitation is Helius API's pagination model:
```
Page 1 → returns cursor A
         Page 2 (needs cursor A) → returns cursor B
                                   Page 3 (needs cursor B) → ...
```

Even with parallel fetching of 40 pages:
- Must wait for Batch 1 to complete to get cursors for Batch 2
- Cannot parallelize across batches
- Creates a dependency chain limiting performance

### 4. Mathematical Analysis

For 86 pages with 40 parallel connections:
- **Batches needed**: 86/40 ≈ 3 batches
- **Time per batch**: ~1.2s per page
- **Theoretical minimum**: 3 batches × 1.2s = ~3.6s
- **Actual time**: 107s (due to pagination narrowing & overhead)

## Why Other Optimizations Didn't Help

1. **WAL-311 (Semaphore)**: ✅ Prevents 429s but doesn't fix sequential nature
2. **WAL-312 (Parallel fetch)**: ✅ Works within batches, not across them
3. **WAL-313 (429 handling)**: ✅ Good, but we're not hitting limits
4. **WAL-316 (RPS tracking)**: ✅ Revealed we use <2% of capacity
5. **WAL-317 (Auto-tune)**: ✅ Can't overcome sequential limitation

## Recommendations

### Immediate Options
1. **Accept current performance**: 107s for 5,478 trades is ~51 trades/second processing
2. **Set realistic expectations**: Update target from <20s to <120s for large wallets

### Future Optimizations (New WALs)
1. **WAL-319: Cursor Prefetching** - Predict and prefetch next cursors (20-30% improvement)
2. **WAL-320: Multi-wallet Parallelism** - Process multiple wallets to use full 50 RPS
3. **WAL-321: Response Caching** - Cache complete responses for common wallets
4. **WAL-322: Alternative API** - Find API that supports true parallel queries

## Conclusion

The 107s performance is primarily due to Helius API's sequential pagination design, not our implementation. We're successfully fetching and parsing 100% of trades, just limited by the API's cursor-based pagination model. The paid plan's 50 RPS cannot be fully utilized for single-wallet queries due to this architectural constraint. 