# Diagnostic Findings - WalletDoctor V4 Parsing Issue

## Executive Summary
Our diagnostic confirms the expert's analysis: We're only parsing 29.5% of SWAP transactions (those with `events.swap`), while 70.5% are ignored. With a tokenTransfers fallback parser, we can parse 96.2% of all swaps.

## Confirmed Root Causes

### 1. Missing Fallback Parser (PRIMARY ISSUE)
- **Current**: Only parsing transactions with `events.swap` (29.5%)
- **Missing**: 70.5% of SWAP transactions have no `events.swap`
- **Solution**: Implement tokenTransfers fallback parser

### 2. Invalid API Query
- **Current**: Attempting `type=SWAP&source=UNKNOWN` → 404 error
- **Fix**: Query `type=SWAP` only (no source parameter)

## Data Analysis (132 transactions)

### DEX Breakdown
| DEX | Total | Has events.swap | Needs Fallback |
|-----|-------|-----------------|----------------|
| PUMP_AMM | 63 | 0 (0%) | 63 (100%) |
| METEORA | 27 | 0 (0%) | 27 (100%) |
| PUMP_FUN | 3 | 0 (0%) | 3 (100%) |
| RAYDIUM | 27 | 27 (100%) | 0 (0%) |
| JUPITER | 12 | 12 (100%) | 0 (0%) |

### Transfer Patterns
- `1_out_1_in`: 49 txs (simple swaps)
- `3_out_1_in`: 36 txs (with fees)
- `2_out_1_in`: 34 txs (with fees)

## Implementation Plan

### Step 1: Fix API Query
```python
# Remove source parameter
params = {
    "type": "SWAP",
    "maxSupportedTransactionVersion": "0"
}
```

### Step 2: Add Fallback Parser
```python
def parse_from_token_transfers(tx):
    transfers = [t for t in tx.get('tokenTransfers', []) 
                 if t.get('tokenStandard') == 'Fungible']
    
    outgoing = [t for t in transfers if t['fromUserAccount'] == wallet]
    incoming = [t for t in transfers if t['toUserAccount'] == wallet]
    
    if outgoing and incoming:
        # Use largest transfers (expert's heuristic)
        largest_out = max(outgoing, key=lambda t: t['tokenAmount'])
        largest_in = max(incoming, key=lambda t: t['tokenAmount'])
        return create_trade(largest_out, largest_in)
```

### Expected Results
- Current: 239 trades (4.2% of 5,646 transactions)
- With fix: ~900-1,100 trades (expert's estimate)
- Parse rate: Should reach ~10-12% of total signatures 