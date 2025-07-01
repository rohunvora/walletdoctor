# WAL-504: MC Calculator with Confidence

## Summary
Implemented market cap calculator that orchestrates supply and price data with confidence levels.

## Implementation Details

### Files Created
- `src/lib/mc_calculator.py` - Market cap calculator with confidence levels
- `tests/test_mc_calculator.py` - Comprehensive test suite

### Features Implemented
1. **MarketCapCalculator class**
   - Orchestrates supply (from Helius) and price (from AMM)
   - Implements confidence levels: high, est, unavailable
   - Integrates with cache for performance
   - Full error handling and logging

2. **Primary Sources (Confidence: "high")**
   - Helius RPC for token supply
   - On-chain AMM pools for price
   - Calculates MC = supply × price

3. **Cache Integration**
   - Checks cache before calculation
   - Stores results after calculation
   - Works without cache if unavailable

4. **Batch Processing**
   - `get_batch_market_caps()` for multiple tokens
   - Parallel execution for efficiency
   - Individual error handling per token

5. **Result Structure**
   ```python
   @dataclass
   class MarketCapResult:
       value: Optional[float]  # Market cap in USD
       confidence: str         # high, est, or unavailable
       source: Optional[str]   # Data source used
       supply: Optional[float] # Token supply (for debugging)
       price: Optional[float]  # Token price (for debugging)
       timestamp: int         # Unix timestamp
   ```

### Test Coverage
- ✅ Primary sources success
- ✅ No supply data handling
- ✅ No price data handling
- ✅ Cache hit scenario
- ✅ Cache miss and store
- ✅ Batch market caps
- ✅ SOL special case
- ✅ Cache error handling
- ✅ Primary source exceptions
- ✅ MarketCapResult dataclass

All 11 tests pass.

### Example Usage
```python
# Single token
result = await calculate_market_cap(
    "So11111111111111111111111111111111111111112",
    slot=250000000,
    timestamp=1700000000
)

if result.value:
    print(f"Market Cap: ${result.value:,.2f}")
    print(f"Confidence: {result.confidence}")
    print(f"Source: {result.source}")

# Batch calculation
calculator = MarketCapCalculator(cache)
results = await calculator.get_batch_market_caps([
    ("token1", 100, 1000),
    ("token2", 200, 2000),
    ("token3", None, None),
])
```

### Fallback Sources (Placeholder)
The `_try_fallback_sources()` method is implemented as a placeholder for future integration with:
- Birdeye historical price API
- DexScreener/Jupiter current price
- Returns None for now

## Next Steps
- WAL-505: Birdeye integration for fallback pricing
- Implement confidence degradation logic
- Add more fallback sources as needed

## Status
✅ Complete - MC calculator with primary sources and confidence levels implemented 