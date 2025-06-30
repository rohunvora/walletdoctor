# Helius API Debug Scripts

These scripts help validate assumptions about the Helius API issues before implementing the v4 solution.

## Prerequisites

Set your API keys:
```bash
export HELIUS_KEY="your_helius_api_key"
export BIRDEYE_API_KEY="your_birdeye_api_key"  # Optional but recommended
```

## Debug Script 1: Transaction Analysis

**Purpose**: Validates whether we're missing swaps and how many use innerSwaps

```bash
python debug_helius_v4.py <wallet_address>

# Example:
python debug_helius_v4.py 3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2
```

**What it tests:**
1. Compares filtered (`type=SWAP`) vs unfiltered transaction fetching
2. Checks how many swaps have `innerSwaps` array (multi-hop trades)
3. Identifies transactions marked as SWAP but missing swap events
4. Shows DEX source distribution

**Expected findings:**
- If filtered count < unfiltered count: We're missing swaps
- If innerSwaps % is high: Current v3 code misses multi-hop trades
- If missing swap events > 0: Some DEXs don't emit standard events

## Debug Script 2: Price Data Availability

**Purpose**: Tests how many tokens have price data available

```bash
python debug_price_data.py <wallet_address>

# Example:
python debug_price_data.py 3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2
```

**What it tests:**
1. Finds all unique tokens traded by the wallet
2. Tests price availability for a sample of tokens
3. Estimates total API calls needed for full history

**Expected findings:**
- Price availability % shows data gaps
- Failed lookups indicate tokens without liquidity data
- API call estimates help plan rate limiting strategy

## Output Files

Both scripts save detailed JSON files:
- `{wallet}_debug_v4.json` - Transaction analysis details
- `{wallet}_price_debug.json` - Price availability details

## Interpreting Results

### ✅ Good signs:
- Filter captures all swaps
- No innerSwaps found
- 90%+ price availability

### ⚠️ Red flags:
- Filtered < unfiltered swap count
- High % of innerSwaps (multi-hop trades)
- Many tokens without price data
- Transactions marked SWAP but no swap event

## Next Steps

Based on the findings:
1. If missing swaps → Implement server-side filters + completeness check
2. If innerSwaps present → Update parser to handle multi-hop trades
3. If price gaps → Implement "priced=false" flagging instead of fallbacks
4. If all good → Current approach might be sufficient!

## Example Output

```
🔍 Debugging Helius API for wallet: 3JoVBiQE...
============================================================

[12:34:56] 🔍 Testing WITH type=SWAP filter...
[12:34:57]   Fetched 87 SWAP transactions
[12:34:58]   → Multi-hop swap found: 3 hops in tx 2Xm9kL8a...

HELIUS API DEBUG SUMMARY
============================================================

Transaction Analysis:
  Total fetched: 87
  Type=SWAP: 87 (100.0%)
  Has swap event: 85 (97.7%)
  Missing swap event: 2

Swap Complexity:
  Simple swaps: 72
  Has innerSwaps: 13 (15.3% of swaps)
  Multi-hop (2+ hops): 8

KEY FINDINGS:
============================================================
⚠️  15.3% of swaps have innerSwaps array (multi-hop trades)
   Current code would miss 8 multi-hop transactions! 