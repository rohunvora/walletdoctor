# WAL-613 Phase B Implementation Plan

## Goal
Implement a proper price strategy that reduces Birdeye API calls while maintaining price accuracy.

## Approach: Helius Prices + Redis Cache

### 1. Extract Helius DEX Prices (2-3 hours)
Many transactions already contain price data from DEX swaps:
- Jupiter swaps include token prices
- Raydium/Orca swaps have price info
- No additional API calls needed

**Implementation:**
```python
# In blockchain_fetcher_v3_fast.py
def extract_helius_price(transaction, token_mint):
    """Extract price from DEX swap if available"""
    if "priceImpactPct" in transaction:
        # Jupiter swap with price data
        return extract_jupiter_price(transaction)
    elif "tokenPriceUSD" in transaction:
        # Direct price data
        return Decimal(transaction["tokenPriceUSD"])
    return None
```

### 2. Redis Cross-Request Cache (2-3 hours)
Share prices between all requests to avoid duplicate Birdeye calls.

**Setup:**
```python
# Railway Redis addon ($5/month)
REDIS_URL=redis://default:password@redis.railway.internal:6379

# Cache structure
prices:{token_mint}:{minute_timestamp} -> price_usd (TTL: 15 min)
```

**Implementation:**
```python
class RedisPriceCache:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL)
    
    async def get_or_fetch(self, token_mint, timestamp):
        # Check Redis first
        key = f"prices:{token_mint}:{minute_ts}"
        cached = self.redis.get(key)
        if cached:
            return Decimal(cached)
        
        # Fetch from Birdeye
        price = await fetch_birdeye_price(token_mint, timestamp)
        
        # Cache for 15 minutes
        self.redis.setex(key, 900, str(price))
        return price
```

### 3. Smart Price Reuse Strategy (1-2 hours)
Implement intelligent price reuse within time windows.

**Rules:**
1. **Same minute**: Always reuse
2. **< 5 minutes**: Reuse for same token
3. **< 15 minutes**: Reuse with "medium" confidence
4. **> 15 minutes**: Fetch fresh price

**Implementation:**
```python
def should_reuse_price(cached_timestamp, request_timestamp):
    age_seconds = (request_timestamp - cached_timestamp).seconds
    
    if age_seconds < 60:  # Same minute
        return True, "high"
    elif age_seconds < 300:  # 5 minutes
        return True, "high"
    elif age_seconds < 900:  # 15 minutes
        return True, "medium"
    else:
        return False, None
```

### 4. Popular Token Pre-warming (1 hour)
Pre-fetch prices for popular tokens on startup.

**Popular Tokens:**
- SOL, USDC, USDT
- BONK, WIF, JTO, JUP
- Top 20 by volume

**Implementation:**
```python
# On startup
async def warm_popular_tokens():
    popular = ["SOL", "USDC", "BONK", ...]
    for token in popular:
        await price_cache.get_or_fetch(token, datetime.now())
```

## Performance Targets

### With Phase B Implementation:
- **First request**: 5-10s (fetch only missing prices)
- **Subsequent requests**: < 0.5s (mostly cache hits)
- **Birdeye calls**: Reduced by 90%+

### API Call Reduction:
- Current: ~22 Birdeye calls per request
- With Helius: ~15 calls (30% from DEX data)
- With Redis: ~2-3 calls (90% cache hits)
- With pre-warming: ~0-1 calls (95%+ cache hits)

## Implementation Order

1. **Day 1 Morning**: Redis setup + basic cache
2. **Day 1 Afternoon**: Helius price extraction
3. **Day 2 Morning**: Smart reuse strategy
4. **Day 2 Afternoon**: Popular token pre-warming
5. **Testing**: Load test with multiple wallets

## Testing Plan

### Test Wallets:
1. Small active trader (current test wallet)
2. Large whale (1000+ positions)
3. New wallet (< 10 trades)
4. Inactive wallet (no recent trades)

### Metrics to Track:
- Response time percentiles (p50, p95, p99)
- Cache hit rate
- Birdeye API calls per request
- Memory usage with Redis

## Alternative: Helius-Only Mode
If Redis setup is delayed, we can ship Helius-only pricing:
- Use DEX prices when available
- Estimate others based on similar tokens
- Mark as "estimated" in price_confidence
- Still meets < 10s target

## Migration Path
1. **Beta**: `?beta_mode=true` (no prices)
2. **v1**: Helius prices + estimates
3. **v2**: Full Redis cache + Birdeye
4. **v3**: Real-time WebSocket prices 