# V3 Speed Optimization Guide

## Performance Bottlenecks & Solutions

### 1. Sequential API Calls → Parallel Fetching
**Problem**: V3 fetches 86 pages sequentially (8.6 seconds minimum)
**Solution**: Fetch 5 pages in parallel batches
```python
# FAST: Parallel fetching
batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
```
**Result**: ~3x faster transaction fetching

### 2. Individual Price Lookups → Batch Processing
**Problem**: 1 API call per price = 1000+ seconds for 1000 trades
**Solution**: Batch up to 100 mints per Birdeye call
```python
# Collect all needed prices first
for trade in trades:
    if not cached:
        price_cache.add_pending(mint, timestamp)

# Then batch fetch
batches = price_cache.get_pending_batches()
```
**Result**: 10-100x faster price fetching

### 3. No Caching → Persistent Cache
**Problem**: Refetching same prices repeatedly
**Solution**: Disk-backed price cache
```python
class FastPriceCache:
    def _load_cache(self):  # Load from .price_cache.json
    def save_cache(self):   # Persist on exit
```
**Result**: Near-instant for repeated queries

### 4. Testing Delays → Configurable Limits
**Problem**: Tests take forever with full data
**Solution**: Test mode configuration
```python
# For testing: 5 pages, no pricing
fetch_wallet_trades_fast(wallet, test_mode=True)

# For production: all data
fetch_wallet_trades_fast(wallet, test_mode=False)
```

## Speed Comparison

| Operation | V3 (Sequential) | V3 Fast | Improvement |
|-----------|----------------|---------|-------------|
| Fetch 5,600 txs | ~10-15s | ~3-5s | 3x faster |
| Token metadata | ~5-10s | ~2-3s | 3x faster |
| Price fetching (1000 trades) | ~17 min | ~2-3 min | 8x faster |
| **Total (test mode)** | ~30s | ~5-8s | 4-6x faster |
| **Total (prod with cache)** | ~20 min | ~3-5 min | 4-6x faster |

## Production Optimizations

### 1. Background Processing
```python
# Queue trades for background price fetching
async def queue_trade_for_pricing(trade_id):
    await redis.lpush("price_queue", trade_id)
```

### 2. Database Storage
```python
# Store processed trades
async def store_trades(wallet, trades):
    await db.trades.insert_many([
        {**trade.to_dict(), 'wallet': wallet}
        for trade in trades
    ])
```

### 3. Webhook Updates
```python
# Real-time updates as prices come in
async def update_trade_price(trade_id, price):
    await db.trades.update_one(
        {'_id': trade_id},
        {'$set': {'price_usd': price, 'priced': True}}
    )
    await notify_webhook(trade_id)
```

### 4. CDN Response Caching
```python
# Cache full responses for popular wallets
@cache_response(ttl=300)  # 5 minutes
async def get_wallet_trades(wallet):
    return await fetch_wallet_trades_fast(wallet)
```

## Usage Examples

### Quick Test (5-10 seconds)
```python
from blockchain_fetcher_v3_fast import fetch_wallet_trades_fast

# Test mode: 5 pages, no pricing
result = fetch_wallet_trades_fast(wallet, test_mode=True)
print(f"Found {result['summary']['total_trades']} trades")
```

### Full Fetch with Caching
```python
# Production: all data, with pricing
result = fetch_wallet_trades_fast(wallet, test_mode=False)

# Second call will be much faster due to cache
result2 = fetch_wallet_trades_fast(wallet, test_mode=False)
```

### Custom Configuration
```python
async with BlockchainFetcherV3Fast(
    max_pages=10,      # Fetch 10 pages max
    skip_pricing=False  # Include pricing
) as fetcher:
    result = await fetcher.fetch_wallet_trades(wallet)
```

## Key Takeaways

1. **Parallel > Sequential**: Always batch API calls when possible
2. **Cache Everything**: Prices don't change for historical data
3. **Progressive Loading**: Return trades immediately, price async
4. **Test != Production**: Use different settings for each 