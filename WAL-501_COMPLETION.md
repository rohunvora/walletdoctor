# WAL-501: Redis MC Cache Infrastructure

## Summary
Implemented Redis-backed market cap cache with in-memory LRU fallback for P5 milestone.

## Changes
- Created `src/lib/mc_cache.py` with:
  - `MarketCapData` dataclass for structured MC storage
  - `InMemoryLRUCache` with TTL and LRU eviction (1000 entry capacity)
  - `MarketCapCache` main class with Redis pooling and automatic fallback
  - Daily granularity caching with 30-day TTL
  - Batch operations for efficient multi-token retrieval
  
- Added comprehensive tests in `tests/test_mc_cache.py`:
  - All data structures and operations tested
  - Redis mocking for CI/CD compatibility
  - Fallback behavior verification
  
- Updated `requirements.txt` with redis==5.0.1

## Key Features
1. **Dual-mode operation**: Redis primary, in-memory fallback
2. **Connection pooling**: Efficient Redis connection management
3. **Daily granularity**: Cache key format `mc:v1:{mint}:{YYYY-MM-DD}`
4. **30-day TTL**: Automatic expiration of old data
5. **Batch operations**: Efficient multi-token MC retrieval
6. **Graceful degradation**: Continues working if Redis unavailable

## Cache Structure
```python
MarketCapData:
  - value: Optional[float]  # Market cap in USD
  - confidence: str         # "high", "est", or "unavailable"
  - timestamp: int          # Unix timestamp when calculated
  - source: Optional[str]   # Data source (e.g., "raydium")
```

## Next Steps
Ready for WAL-502: Helius supply fetcher implementation 