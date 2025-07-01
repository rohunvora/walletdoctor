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