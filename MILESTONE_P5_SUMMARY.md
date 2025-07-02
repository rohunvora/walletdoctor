# MILESTONE P5: Multi-tier pricing + Fallbacks

## Phase Summary
Implement a multi-tiered pricing system with fallback options for maximum reliability.

## Tasks

### WAL-501: Birdeye multi-source prices ✅
**Status:** Complete
- Implemented weighted average pricing from multiple exchanges
- Filters exchanges by minimum 10 SOL volume
- Uses median of top 3 exchanges by volume
- Comprehensive test coverage with mocked responses

### WAL-502: Helius token accounts supply ✅
**Status:** Complete
- Implemented on-chain supply calculation
- Fetches top 20 token accounts
- Considers active supply based on 30-day activity
- Filters circulating vs total supply

### WAL-503: On-chain AMM price reader ✅
**Status:** Complete
- Reads prices from Raydium/Orca pools
- Filters pools by TVL ≥$5k
- Calculates price from deepest pool
- SOL price caching for TVL calculations

### WAL-504: Historical price cache ✅
**Status:** Complete
- SQLite database with WAL mode for concurrency
- Auto-cache successful lookups with metadata
- 7-day retention with background cleanup
- Hit/miss tracking and performance stats

### WAL-505: Tiered price service ✅
**Status:** Complete
- Three-tier fallback: Birdeye → AMM → Cache → Error
- Configurable timeout per tier (5s, 10s, 0.1s defaults)
- Automatic caching and detailed statistics
- Enable/disable individual tiers

## Implementation Details

### Multi-Source Pricing (WAL-501)
```python
# Birdeye multi-exchange aggregation
prices = await get_birdeye_multi_source_price(token_address)
# Returns: {"price": 0.123, "sources": 3, "volume": 15000}
```

### Supply Calculation (WAL-502)
```python
# On-chain supply analysis
supply = await get_token_supply(token_address)
# Returns: {"total": 1000000, "circulating": 800000, "active": 600000}
```

### AMM Price Reader (WAL-503)
```python
# Direct on-chain pool prices
price_data = await get_amm_price(token_mint, USDC_MINT)
# Returns: (Decimal("150.0"), "raydium", Decimal("300000"))
```

### Historical Price Cache (WAL-504)
```python
# Cache prices with automatic cleanup
async with PriceCache() as cache:
    await cache.store_price(token_mint, quote_mint, price, source)
    cached = await cache.get_price(token_mint, quote_mint, max_age_seconds=3600)
```

### Tiered Price Service (WAL-505)
```python
# Unified service with automatic fallback
async with TieredPriceService() as service:
    result = await service.get_price(token_mint)
    # Automatically tries: Birdeye → AMM → Cache
    print(f"Price: ${result.price} from {result.tier.value}")
```

## Benefits
1. **Reliability**: Multiple fallback options ensure pricing availability
2. **Accuracy**: Cross-reference prices from different sources
3. **Performance**: Caching reduces API calls
4. **Cost**: Fallbacks prevent expensive retries

## Testing Coverage
- Unit tests for each pricing module
- Integration tests for fallback scenarios
- Mock responses for API testing
- Performance benchmarks for cache hits

## Milestone P5 Complete! ✅

All 5 tasks have been successfully implemented:
1. ✅ WAL-501: Birdeye multi-source prices (MC cache)
2. ✅ WAL-502: Helius token accounts supply
3. ✅ WAL-503: On-chain AMM price reader
4. ✅ WAL-504: Historical price cache
5. ✅ WAL-505: Tiered price service

## Production Integration

The tiered pricing system is ready for integration with the main API:
1. Replace single-source pricing with TieredPriceService
2. Configure timeouts based on endpoint requirements
3. Monitor tier usage statistics for optimization
4. Adjust cache retention based on usage patterns

## Performance Benefits

- **Reduced API costs**: Cache hits avoid expensive external calls
- **Higher availability**: Multiple fallback options
- **Better latency**: Fast cache lookups for repeated queries
- **Real-time monitoring**: Statistics for each pricing tier 