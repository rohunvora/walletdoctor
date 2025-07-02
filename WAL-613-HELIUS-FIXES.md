# WAL-613 Helius-Only Pricing - Fixes Applied

## Issue Identified
`PRICE_HELIUS_ONLY=true` was set in Railway but Birdeye was still being called because:
- BlockchainFetcherV3Fast was checking `skip_pricing` but NOT `PRICE_HELIUS_ONLY`
- This caused the 45+ second Birdeye bottleneck to persist

## Fixes Applied

### 1. Fixed BlockchainFetcherV3Fast (`src/lib/blockchain_fetcher_v3_fast.py`)
```python
# Step 6: Fetch prices (batch optimized)
if os.getenv('PRICE_HELIUS_ONLY', '').lower() == 'true':
    self._report_progress("Skipping Birdeye - using Helius-only pricing")
elif not self.skip_pricing:
    await self._fetch_prices_batch(filtered_trades)
else:
    self._report_progress("Skipping price fetching")
```

### 2. Added Startup Logging (`src/api/wallet_analytics_api_v4_gpt.py`)
- `[BOOT] PRICE_HELIUS_ONLY: {value}` - logged at startup
- `[REQUEST] PRICE_HELIUS_ONLY={value}` - logged per request
- `[PHASE]` tags for timing breakdown

### 3. Enhanced Phase Timing
- `[PHASE] Starting position fetch...`
- `[PHASE] helius_fetch completed in X.XXs`
- `[PHASE] position_build completed in X.XXs`
- `[PHASE] price_fetch completed in X.XXs`

### 4. Added 404 Debug Logging
- Logs sample mint addresses that get 404s from Birdeye
- Will help identify if invalid/old mints are being requested

## Expected Behavior After Deploy

With these fixes:
1. **No Birdeye calls** when `PRICE_HELIUS_ONLY=true`
2. **Log output** will show:
   - `[BOOT] PRICE_HELIUS_ONLY: true` at startup
   - `Skipping Birdeye - using Helius-only pricing` during fetch
   - `[PRICE] Helius-only mode: XXX transactions available`
3. **Performance**: <8s cold, <0.5s warm

## Quick Test Command
```bash
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
  -m 10
```

## Git Commit
All changes are committed and pushed to main branch. 