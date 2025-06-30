# WalletDoctor V4 Debug Summary for Expert Review

## Current Issue
We're only parsing 4.2% of SWAP transactions (239 out of 5,646) when we expect ~800-1,100 trades.

## Key Findings

### Transaction Analysis (First 202 SWAP transactions)
- **With swap event**: 66 (32.7%)
- **Without swap event**: 136 (67.3%)

### DEX Distribution
- PUMP_AMM: 42.1% (mostly WITHOUT swap events)
- RAYDIUM: 24.3% (mostly WITH swap events)
- METEORA: 22.8% (mixed)
- JUPITER: 8.4% (mixed)
- PUMP_FUN: 2.5%

## Implementation Status

### ✅ Working
1. Pagination fix - now fetching ~5,600 SWAP transactions (vs 35 before)
2. Multi-hop collapse - avoiding duplication
3. Guard clauses for missing `rawTokenAmount`

### ❌ Not Working
1. Only parsing transactions with `events.swap` (32.7% of total)
2. No fallback parser for the 67.3% without swap events
3. Attempted `type=SWAP&source=UNKNOWN` returns 404

## Questions for Expert

1. **How to parse the 67.3% of SWAP transactions without `events.swap`?**
   - Should we use `tokenTransfers` array?
   - Different approach for each DEX (PUMP_AMM seems to never have swap events)?

2. **Is our 4.2% parse rate normal or indicative of a bug?**
   - We successfully parse 66 out of 202 transactions (32.7%)
   - But overall only 239 out of 5,646 (4.2%)

3. **Correct API query strategy?**
   - Current: Single pass with `type=SWAP`
   - Should we query other transaction types?

## Files to Review
1. `transaction_format_analysis.json` - Raw transaction examples
2. `blockchain_fetcher_v2.py` - Current implementation
3. `test_blockchain_fetcher_v2.py` - Test showing metrics

## Sample Transaction Without Swap Event
```json
{
  "signature": "...",
  "source": "PUMP_AMM",
  "type": "SWAP",
  "events": {},  // No swap event!
  "tokenTransfers": [
    // Token transfer data available
  ]
}
``` 