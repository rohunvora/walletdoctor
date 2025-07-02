# Market Cap Cache Documentation

## Overview
The market cap subsystem uses a two-tier caching strategy:
1. Redis cache (primary) with 24-hour TTL
2. In-memory LRU cache (fallback) with 5-minute TTL

## Price Calculation Pipeline

### Primary Sources (High Confidence)
1. **Helius Supply API** - Gets token supply at specific slot
2. **AMM Price Reader** - Reads on-chain pool prices from:
   - Raydium pools
   - Orca whirlpools  
   - Pump.fun bonding curves

### Fallback Sources (Est Confidence)
1. **Birdeye API** - Direct market cap or price data
2. **Jupiter API** - Price quotes (skipped for pump.fun tokens)
3. **DexScreener API** - Last resort price/MC data

## Debugging Tools

### debug_price_at_slot.py
A diagnostic script to inspect price calculation at specific slots.

**Usage:**
```bash
export HELIUS_KEY=your_key_here
export BIRDEYE_API_KEY=your_key_here  # Optional
python3 scripts/debug_price_at_slot.py
```

**Output Example:**
```
fakeout first buy
  mint: GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump
  slot: 336338086
  AMM price: $0.00006300
  source: pump_amm
  TVL: $126
  pump pool: FCFFnCLc35Tx9fss7AKLUBmdsP6S9GbbrVhvTrt379A9
  birdeye (current): $0.00003989
  difference: +57.9%
```

The script helps identify:
- Which AMM pool is selected
- Pool reserves and TVL
- Price calculation accuracy
- Source confidence level

### Key Features
1. **Pool Selection Logic**:
   - Primary: TVL ≥ $1,000 → "high" confidence
   - Fallback: TVL ≥ $100 → "medium" confidence  
   - Last resort: Any TVL → "low" confidence

2. **Pump.fun Token Handling**:
   - Detects tokens ending with "pump"
   - Uses virtual + real reserves for price
   - Only real reserves count for TVL
   - Skips Jupiter quotes entirely

3. **Supply Assumptions**:
   - Most Solana tokens: 1 billion supply
   - Some exceptions exist (always verify on-chain)

## Cache Configuration

### Redis Setup
```python
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = 86400  # 24 hours
```

### Fallback Behavior
When Redis is unavailable:
1. System automatically falls back to in-memory LRU cache
2. Cache size: 10,000 entries max
3. TTL: 300 seconds (5 minutes)
4. No persistence between restarts

### Testing Cache Fallback
```python
# Test with Redis down
export REDIS_URL="redis://invalid:6379"
python3 -m pytest tests/test_mc_cache.py::test_fallback_to_memory_cache
```

## Accuracy Requirements
- Market cap calculations must be within ±10% of expected values
- Use `tests/accuracy/` test suite to verify
- Run with paid API keys for full coverage

## Common Issues

### Issue: Inflated Market Caps
**Cause**: Using Jupiter quotes for pump.fun tokens
**Fix**: AMM price reader now skips Jupiter for pump tokens

### Issue: Low Confidence Warnings
**Cause**: Pool TVL below $1,000
**Fix**: System still returns price but marks as "medium" or "low" confidence

### Issue: No Price Data
**Cause**: No AMM pools found and all fallbacks failed
**Fix**: Returns confidence="unavailable" with null market cap 

## Position Cache Documentation (WAL-607)

### Overview
The position cache provides fast access to wallet positions and unrealized P&L data using:
1. **Redis cache** (primary) with configurable TTL
2. **In-memory LRU cache** (fallback) with size-based eviction
3. **Staleness marking** for cache freshness management
4. **Lazy refresh** for background data updates

### Configuration

#### Environment Variables
```bash
# Enable/disable position caching (default: true)
POSITION_CACHE_ENABLED=true

# Cache time-to-live in seconds (default: 900 = 15 minutes)
POSITION_CACHE_TTL_SEC=900

# Maximum number of wallets in LRU cache (default: 2000)
POSITION_CACHE_MAX=2000
```

### Cache Key Structure
```
pos:v1:position:{wallet}:{token_mint}  # Individual positions
pos:v1:snapshot:{wallet}               # Portfolio snapshots
pos:v1:pnl:{wallet}:{token_mint}      # Position P&L data
```

### Eviction Policy

#### Time-Based (TTL)
- Default: 15 minutes for positions
- 1 minute for P&L data (price-sensitive)
- 30 minutes for portfolio snapshots

#### Size-Based (LRU)
- Max 2,000 wallets in memory cache
- Least Recently Used eviction
- Access moves items to end of queue

### Staleness & Refresh

#### Staleness Detection
Data is marked stale when:
- Age > POSITION_CACHE_TTL_SEC
- Redis TTL < 50% of original

#### Lazy Refresh Pattern
```
1. Client requests /v4/positions/{wallet}
2. Cache returns stale data with {"stale": true}
3. Background refresh triggered automatically
4. Next request gets fresh data
```

#### API Response Example
```json
{
  "wallet": "34zYDgjy...",
  "positions": [{
    "token_mint": "...",
    "balance": "100",
    "stale": true  // Added when data is stale
  }],
  "cached": true,
  "stale": true,
  "age_seconds": 1200  // Age of cached data
}
```

### Metrics (Prometheus-Ready)

Available at `/metrics` endpoint:
- `position_cache_hits` - Successful cache retrievals
- `position_cache_misses` - Cache misses requiring calculation
- `position_cache_evictions` - LRU evictions due to size limit
- `position_cache_refresh_errors` - Failed refresh attempts
- `position_cache_stale_serves` - Stale data served to clients
- `position_cache_refresh_triggers` - Background refreshes initiated

### Cache Invalidation

#### Automatic Triggers
- New trades detected for wallet
- Manual refresh via `?refresh=true` parameter
- Position updates via API

#### Pattern-Based Invalidation
```python
# Invalidates all cached data for a wallet
await cache.invalidate_wallet("wallet_address")
```

### Performance Targets

#### Latency Requirements
- Cache reads: < 0.1ms (in-memory)
- Cache writes: < 0.5ms
- P95 API response: < 120ms with cache
- Fresh calculation: < 500ms for 50 positions

#### Capacity Planning
- 2,000 wallets × ~10 positions each
- ~100KB per wallet snapshot
- ~200MB total memory footprint

### Monitoring & Debugging

#### Health Check
```bash
curl http://localhost:8080/health
```

Returns cache statistics:
```json
{
  "cache_stats": {
    "enabled": true,
    "backend": "redis",
    "hit_rate_pct": 85.5,
    "lru_size": 1523,
    "active_refresh_tasks": 3
  }
}
```

#### Force Refresh
```bash
# Force fresh data (bypasses cache)
curl http://localhost:8080/v4/positions/{wallet}?refresh=true
```

### Common Issues

#### Issue: High Memory Usage
**Cause**: Too many wallets cached
**Fix**: Reduce POSITION_CACHE_MAX or decrease TTL

#### Issue: Stale Data Complaints
**Cause**: TTL too high for volatile tokens
**Fix**: Lower POSITION_CACHE_TTL_SEC or use refresh parameter

#### Issue: Slow Initial Requests
**Cause**: Cache misses requiring full calculation
**Fix**: Pre-warm cache for active wallets or implement predictive caching 