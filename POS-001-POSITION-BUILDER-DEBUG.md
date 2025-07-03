# POS-001: Position Builder Returns Empty Positions

**Status**: New  
**Priority**: High  
**Labels**: `bug`, `position-builder`, `blocked-on-scope`  
**Blocking**: v0.7.1-pos-alpha  

## Problem Statement

The position builder pipeline is returning empty positions array despite having valid trades, resulting in empty portfolio responses for wallets with trading history.

**Discovered during**: TRD-001 debugging session  
**Test wallet**: `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`

## Evidence from TRD-001 Debug Session

### ✅ Trades Pipeline Working
- Signatures fetched: **1713** (confirmed working)
- Trades extracted: **1091** (confirmed working)  
- Trade structure: Valid and complete

### ❌ Position Builder Failing
- Raw positions built: **Unknown** (needs investigation)
- Positions after filter: **0** (confirmed failing)
- Expected: Should have multiple open positions

## Debug Approach

### Phase 1: Position Builder Investigation
Add debug logs to track position building pipeline:

1. **Raw position building** (`PositionBuilder.build_positions_from_trades()`)
   - Log trade count input
   - Log raw positions output before filtering
   - Track position opening/closing logic

2. **Position filtering** (`PositionSnapshot.from_positions()`)
   - Log positions before/after filtering
   - Identify what criteria is filtering out positions
   - Check for balance thresholds, date filters, etc.

### Phase 2: Cost Basis Analysis
Investigate cost basis calculation issues:

1. Check FIFO/LIFO logic in position tracking
2. Validate trade aggregation by token
3. Ensure position closing detection is accurate

### Phase 3: Integration Testing
Create isolated tests for:

1. Position builder with known trade sequences
2. Edge cases (small balances, rapid trades, etc.)
3. Compare against expected vs actual positions

## Implementation Plan

### Debug Infrastructure
```python
# Add to PositionBuilder
logger.info(f"[POS-DEBUG] Processing {len(trades)} trades for {wallet}")
positions = self.build_positions_from_trades(trades, wallet)
logger.info(f"[POS-DEBUG] Built {len(positions)} raw positions")

# Add to filtering logic
logger.info(f"[POS-DEBUG] Filtering {len(position_pnls)} position PnLs")
filtered = [p for p in position_pnls if meets_criteria(p)]
logger.info(f"[POS-DEBUG] {len(filtered)} positions after filtering")
```

### Test Cases
1. **Test wallet**: `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`
2. **Small wallet**: Wallet with 1-2 positions
3. **Edge case wallet**: Wallet with closed positions only

## Acceptance Criteria

- [ ] Position builder correctly processes trades into positions
- [ ] Debug logs identify exact point where positions are lost
- [ ] Root cause documented with fix implemented
- [ ] Test wallet shows expected open positions (>0)
- [ ] Unit tests cover the identified edge cases

## Related Issues

- **TRD-001**: ✅ Complete - Trades export working perfectly
- **Blocks**: v0.7.1-pos-alpha release
- **Depends on**: Position builder scope clarification

## Notes

- Keep TRD-001 trades endpoint completely separate
- This is purely a position calculation bug
- Pricing pipeline investigation can wait until positions are fixed
- No urgency for GPT team - they have working trades endpoint

## Next Release Train

- **v0.7.1-pos-alpha**: Fix position builder (this ticket)
- **v0.8.0-prices**: Re-enable pricing with Helius-only
- **v0.9.x**: Redis warm-cache & pagination 