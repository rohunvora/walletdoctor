# Helius-Only Pricing Design (PRC-001)

**Goal**: Populate `current_price_usd` and `current_value_usd` for trades & positions using a single SOL/USD spot price for consistent, trader-friendly pricing.

## Problem Statement

Currently, positions show `$0.00` for all `current_price_usd` values, preventing ChatGPT from discussing dollar values meaningfully. Users need consistent SOL-denominated pricing that can be converted to USD using current market rates.

## Design Approach: Single SOL Spot Price

Instead of token-by-token pricing (complex, slow, error-prone), we use **one SOL/USD spot price** applied consistently across all positions.

### Benefits
- **Consistent**: No discrepancies between different price sources
- **Fast**: Single API call vs hundreds of token lookups  
- **Reliable**: Robust fallback chain for SOL price
- **Trader-friendly**: All values use same exchange rate

### Trade-offs
- **Approximate**: Assumes all tokens priced in SOL terms
- **Less precise**: Not actual current token/USD rates
- **Good enough**: For ChatGPT analysis, consistency > precision

## Implementation Plan

### 1. SOL Price Source Chain

**Primary**: CoinGecko public API (Helius price oracle reserved for future enhancement)
```python
# GET https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd
fallback_price = coingecko_client.get_sol_price()
```

**Cache**: 30-second in-memory TTL
```python
@lru_cache(maxsize=1)
@timed_cache(ttl=30)
def get_sol_price_usd() -> Decimal:
    """Returns current SOL/USD price with 30s cache"""
```

### 2. Pipeline Integration

**Injection Point**: `UnrealizedPnLCalculator.calculate_batch_unrealized_pnl()`

```python
# Check if we should use SOL spot pricing (PRC-001)
if should_calculate_unrealized_pnl() and should_use_sol_spot_pricing():
    sol_price_usd = get_sol_price_usd()
    
    for position in positions:
        if position.balance > 0:
            current_value_usd = position.balance * sol_price_usd
            # Apply to all positions consistently
```

### 3. Failure Behavior

**Graceful Degradation**: 
- Price fetch fails → `current_price_usd = null`
- Pipeline continues normally
- Position data still usable for non-dollar analysis

**Error Logging**: 
```python
try:
    sol_price = get_sol_price_usd()
except Exception as e:
    logger.warning(f"SOL price fetch failed: {e}")
    sol_price = None
```

### 4. Feature Flag Control

**Environment Variable**: `PRICE_SOL_SPOT_ONLY=true`

**Default**: `false` (preserve current behavior)

**Quick Toggle**: Can disable instantly if issues arise

## API Response Changes

### Position Response Format (v0.8.0-prices)

#### Before (POS-002)
```json
{
  "positions": [
    {
      "token_symbol": "BONK",
      "balance": "1000000.123456",
      "cost_basis_usd": "85.50",
      "current_price_usd": null,
      "current_value_usd": null,
      "unrealized_pnl_usd": null,
      "unrealized_pnl_pct": null,
      "price_confidence": "unavailable"
    }
  ]
}
```

#### After (PRC-001) - Success Case
```json
{
  "positions": [
    {
      "token_symbol": "BONK",
      "balance": "1000000.123456", 
      "cost_basis_usd": "85.50",
      "current_price_usd": "180.45",
      "current_value_usd": "180450000.23",
      "unrealized_pnl_usd": "180449914.73",
      "unrealized_pnl_pct": "211207851.58",
      "price_confidence": "est",
      "price_source": "sol_spot_price",
      "last_price_update": "2024-01-15T18:30:45.123Z"
    }
  ]
}
```

#### After (PRC-001) - Failure Case (Graceful Degradation)
```json
{
  "positions": [
    {
      "token_symbol": "BONK",
      "balance": "1000000.123456",
      "cost_basis_usd": "85.50", 
      "current_price_usd": null,
      "current_value_usd": null,
      "unrealized_pnl_usd": null,
      "unrealized_pnl_pct": null,
      "price_confidence": "unavailable",
      "price_source": null,
      "last_price_update": "2024-01-15T18:30:45.123Z"
    }
  ]
}
```

### Key Response Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `current_price_usd` | `string\|null` | SOL spot price when `PRICE_SOL_SPOT_ONLY=true` | `"180.45"` |
| `current_value_usd` | `string\|null` | `balance * current_price_usd` | `"1804.50"` |
| `price_confidence` | `enum` | `"est"` for SOL pricing, `"unavailable"` on failure | `"est"` |
| `price_source` | `string\|null` | Always `"sol_spot_price"` when PRC-001 active | `"sol_spot_price"` |

## Schema Versioning

**Version**: `v0.8.0-prices`
**Changes**: 
- `current_price_usd`: reflects SOL spot price when `PRICE_SOL_SPOT_ONLY=true`
- `price_source`: new field indicating `"sol_spot_price"` for PRC-001
- May be `null` if price fetch fails (graceful degradation)

## Performance Targets

- **SOL price fetch**: <200ms (typically ~100ms from CoinGecko)
- **Cache hit**: <1ms  
- **Total position endpoint**: <5s (down from 8s)
- **Price failure rate**: <1%

## Testing Strategy

### Unit Tests
- ✅ `test_sol_price_fetcher()` - CoinGecko + caching (13 tests)
- ✅ `test_prc_001_integration()` - Position pricing integration
- ✅ `test_graceful_degradation()` - Null handling and failures

### Integration Tests  
- Demo wallet SOL pricing validation
- End-to-end position response format verification
- Cache TTL and performance testing

### CI Monitoring
- **Alert**: if `current_price_usd` is null in >10% of positions
- **Metric**: SOL price fetch success rate >99%
- **Performance**: Position endpoint latency <5s p95

## Production Deployment

### Phase 1: Controlled Rollout
1. Deploy with `PRICE_SOL_SPOT_ONLY=false` (default off)
2. Validate all existing functionality unchanged
3. Monitor baseline performance

### Phase 2: Feature Testing  
1. Enable `PRICE_SOL_SPOT_ONLY=true` on staging/temp deployment
2. Test demo wallets (34zYD..., AAXT...)
3. Verify expected JSON response format

### Phase 3: Production Enable
1. Set `PRICE_SOL_SPOT_ONLY=true` in production
2. Monitor price fetch success rate
3. Validate ChatGPT can now discuss dollar values

## Success Criteria

✅ **Functional**: Demo wallet returns positions with `current_price_usd` != null  
✅ **Performance**: Position endpoint <5s total  
✅ **Reliability**: <1% price fetch failure rate  
✅ **UX**: ChatGPT can discuss dollar values meaningfully

## Testing Commands

```bash
# Enable SOL spot pricing
export PRICE_SOL_SPOT_ONLY=true

# Test small demo wallet
curl -H "X-Api-Key:$API_KEY" \
  "$URL/v4/positions/export-gpt/34zYDgjy..." \
  | jq '.positions[0] | {token: .token_symbol, price: .current_price_usd, value: .current_value_usd}'

# Expected output:
# {
#   "token": "BONK",
#   "price": "180.45", 
#   "value": "1804500.23"
# }
``` 