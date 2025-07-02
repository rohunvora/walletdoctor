# WAL-511: Real-wallet MC accuracy test

## Summary
Fixed market cap calculation accuracy by ensuring pump.fun tokens use on-chain reserve prices instead of Jupiter quotes, and added comprehensive test suite to validate real trades.

## Changes Made

### 1. Enhanced AMM Price Reader
- Modified `src/lib/amm_price.py` to fetch pump.fun pool reserves
- Added TVL threshold check ($3k minimum)
- Proper price calculation from reserve ratios

### 2. Fixed MC Calculator Logic
- Updated `src/lib/mc_calculator.py` to prioritize AMM prices for pump tokens
- Removed Jupiter quote fallback for pump.fun tokens when pools exist
- Added proper confidence tagging based on data source

### 3. Created Accuracy Test Suite
- `tests/test_mc_real_trades.py` - Validates 6 real trades
- JSON fixture with expected values
- Asserts MC within ±10% tolerance
- Validates PNL accuracy within ±0.1 SOL

## Test Results
```bash
pytest tests/test_mc_real_trades.py -v
# All 6 trade validations pass
# Market caps within tolerance
# Confidence levels all "high"
```

## Files Changed
- `src/lib/amm_price.py` - Added pump.fun pool fetching
- `src/lib/mc_calculator.py` - Fixed price source priority
- `tests/test_mc_real_trades.py` - New accuracy test
- `tests/fixtures/real_trades.json` - Expected values fixture 