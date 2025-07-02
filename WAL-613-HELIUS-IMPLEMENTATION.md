# WAL-613 Helius-Only Pricing Implementation

## Summary
Implemented Helius-only pricing to replace Birdeye and eliminate the 42+ second bottleneck.

## Files Created/Modified

### 1. `src/lib/helius_price_extractor.py`
- Extracts token prices from DEX swap transactions
- Parses Helius transaction data to find SOL/token swaps
- Calculates USD price using SOL price at transaction slot
- Maintains 6-hour in-memory price cache
- Falls back to cached prices if no swap found

### 2. `src/lib/unrealized_pnl_calculator.py`
- Added support for `PRICE_HELIUS_ONLY` environment variable
- Modified to accept transactions and trades from API
- Batch extracts prices from all transactions at once
- Bypasses market cap calculator when Helius-only mode is enabled

### 3. `src/api/wallet_analytics_api_v4_gpt.py`
- Passes transactions and trades to UnrealizedPnLCalculator
- Only when `PRICE_HELIUS_ONLY=true`

### 4. `src/lib/blockchain_fetcher_v3_fast.py`
- Modified to include transactions in response when `PRICE_HELIUS_ONLY=true`
- Preserves full transaction data for price extraction

### 5. `scripts/test_helius_price_only.py`
- Test script to validate Helius price extraction
- Measures performance and coverage

## How It Works

1. **Transaction Fetching**: BlockchainFetcherV3Fast fetches all swap transactions
2. **Price Extraction**: HeliusPriceExtractor parses swap events to find:
   - Direct SOL/token swaps (primary source)
   - Token transfers that imply swaps (fallback)
3. **Price Calculation**: 
   - Extracts token amounts from swap
   - Gets SOL price at that slot
   - Calculates: `token_price = (SOL_amount / token_amount) * SOL_price_USD`
4. **Caching**: Prices cached for 6 hours in memory
5. **Coverage**: Returns null price if no swap data available

## Environment Variables

```bash
# Enable Helius-only pricing
PRICE_HELIUS_ONLY=true

# Also ensure these are set
POSITIONS_ENABLED=true
UNREALIZED_PNL_ENABLED=true
```

## Performance Target
- Cold cache: < 8 seconds
- Warm cache: < 0.5 seconds

## Next Steps

1. **Test with real API keys** to validate performance
2. **Deploy to Railway** with `PRICE_HELIUS_ONLY=true`
3. **Monitor coverage** - what % of tokens get priced
4. **Implement Redis cache** (Phase B) if needed for cross-request caching

## Known Limitations

1. **SOL Price**: Currently using hardcoded $145 - should fetch from Pyth/Helius
2. **Coverage**: Only tokens with recent swaps get priced
3. **Accuracy**: Prices from swaps may differ from spot prices

## Testing

```bash
# Set environment variables
export HELIUS_KEY=your_actual_key
export BIRDEYE_API_KEY=your_actual_key  # Still needed for other endpoints
export PRICE_HELIUS_ONLY=true
export POSITIONS_ENABLED=true

# Run test
python3 scripts/test_helius_price_only.py

# Test GPT export endpoint
curl -X GET "http://localhost:8081/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
  -H "X-Api-Key: wd_test1234567890123456789012345678"
``` 