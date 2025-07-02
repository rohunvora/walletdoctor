# WAL-600: P6 Design Document - Unrealized P&L & Open Position Tracking

## Problem Statement

The current WalletDoctor API (V3/V4) successfully tracks realized P&L from completed trades but lacks visibility into:
- **Open positions**: Tokens currently held that haven't been fully sold
- **Unrealized P&L**: Paper gains/losses on holdings based on current market prices
- **Position history**: How holdings evolved over time
- **Cost basis**: Entry prices for partial fills and multi-buy scenarios

This gap prevents users from understanding their complete portfolio performance and making informed decisions about open positions.

## Data Architecture

### Existing Data We Have

From the current `Trade` dataclass:
- `token_in_mint`, `token_out_mint`: Token addresses involved
- `token_in_amount`, `token_out_amount`: Exact amounts traded
- `timestamp`: When the trade occurred
- `slot`: Blockchain slot number
- `price_usd`, `value_usd`: Historical prices at trade time
- `pnl_usd`: Realized P&L (currently only for closed positions)

### New Data Required

1. **Position Tracking**
   ```python
   @dataclass
   class Position:
       wallet: str
       token_mint: str
       token_symbol: str
       balance: Decimal  # Current holding
       cost_basis: Decimal  # Weighted avg or FIFO cost
       cost_basis_usd: Decimal  # USD value at entry
       last_update_slot: int
       last_update_time: datetime
   ```

2. **Position P&L**
   ```python
   @dataclass
   class PositionPnL:
       position: Position
       current_price_usd: Decimal
       current_value_usd: Decimal
       unrealized_pnl_usd: Decimal
       unrealized_pnl_pct: Decimal
       price_confidence: str  # "high", "est", "stale"
       last_price_update: datetime
   ```

3. **Enhanced Trade Data**
   - Add `remaining_balance` after each trade
   - Add `cost_basis_method` used ("fifo" or "weighted_avg")
   - Add `position_closed` boolean flag

## Algorithm Flow

### 1. Open vs Closed Trade Detection

```
FOR each trade in chronological order:
    IF trade.action == "buy":
        Add to position
        Update cost basis
    ELSE IF trade.action == "sell":
        Reduce position
        Calculate realized P&L
        IF remaining_balance == 0:
            Mark position as closed
        ELSE:
            Mark as partial sell
```

### 2. Cost Basis Calculation

#### FIFO (First In, First Out)
```python
def calculate_fifo_cost_basis(buys: List[Trade], sell_amount: Decimal):
    remaining_to_sell = sell_amount
    total_cost = Decimal(0)
    
    for buy in buys:  # chronological order
        if remaining_to_sell <= 0:
            break
        amount_from_this_buy = min(buy.amount, remaining_to_sell)
        total_cost += amount_from_this_buy * buy.price
        remaining_to_sell -= amount_from_this_buy
    
    return total_cost / sell_amount if sell_amount > 0 else 0
```

#### Weighted Average
```python
def calculate_weighted_avg_cost_basis(buys: List[Trade]):
    total_amount = sum(buy.amount for buy in buys)
    total_cost = sum(buy.amount * buy.price for buy in buys)
    return total_cost / total_amount if total_amount > 0 else 0
```

### 3. Unrealized P&L Calculation

```
1. Identify all open positions (balance > 0)
2. Fetch current market prices (with caching)
3. FOR each position:
    current_value = balance * current_price
    unrealized_pnl = current_value - cost_basis_usd
    unrealized_pnl_pct = (unrealized_pnl / cost_basis_usd) * 100
4. Tag confidence level based on price source/age
```

### 4. Re-valuation Cadence

- **On-demand**: Fresh prices when API is called
- **Cached prices**: 60-second TTL for frequently accessed tokens
- **Stale price detection**: Mark prices > 5 minutes old as "stale"
- **Streaming updates**: SSE endpoint emits position updates every 30s

## Edge-Case Matrix

| Case | Description | Solution | Impact |
|------|-------------|----------|---------|
| **Partial Fills** | Multiple buys/sells at different prices | Track each transaction separately, apply cost basis method | Accurate P&L calculation |
| **Airdrops** | Tokens received without purchase | Set cost basis to 0, flag as "airdrop" type | 100% unrealized gain |
| **Dust Amounts** | Tiny leftover balances < $0.01 | Ignore in position tracking, log as "dust" | Cleaner position list |
| **Token Splits/Migrations** | Token contract changes | Map old→new mint addresses, adjust amounts | Continuity in tracking |
| **Failed Transactions** | Reverted trades in blockchain | Filter by success status before processing | No false positions |
| **MEV Sandwich** | Multiple trades in same slot | Use transaction index for ordering | Correct FIFO ordering |
| **LP Positions** | Liquidity pool tokens | Track as separate position type with special handling | Future enhancement |
| **Leveraged Positions** | Borrowed funds for trading | Flag leverage trades, track borrow costs | Accurate net P&L |

## Performance & Accuracy Targets

### Performance SLAs
- Position calculation: < 100ms for 1000 trades
- Price fetching: < 500ms for 50 unique tokens (with cache)
- Full wallet analysis with positions: < 10s for large wallets
- Memory usage: < 100MB for 10k trade history

### Accuracy Targets
- Cost basis: Exact to 8 decimal places
- Unrealized P&L: ±0.1% vs manual calculation
- Price freshness: 95% of prices < 60s old
- Position balance: Exact match with on-chain state

### Cache Strategy
```
1. Position Cache (Redis)
   - Key: wallet:token_mint:position
   - TTL: 5 minutes
   - Invalidate on new trades

2. Price Cache (existing)
   - Enhanced with batch pre-warming
   - Priority queue for active positions

3. Balance Cache
   - Key: wallet:token_mint:balance
   - TTL: 30 seconds
   - Refresh on-demand if stale
```

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|---------|------------|
| **Rate Limits** | Medium | High | Use existing RateLimitedFetcher, batch price requests |
| **Price Gaps** | High | Medium | Fallback to last known price, mark as "stale" |
| **Division by Zero** | Low | Low | Defensive checks, return 0 for edge cases |
| **Memory Overflow** | Low | High | Streaming processing, position limits (top 100) |
| **Calculation Errors** | Medium | High | Comprehensive unit tests, property-based testing |
| **Stale Positions** | Medium | Low | Background refresh job, TTL on cached data |
| **Chain Reorgs** | Low | Medium | Use finalized slots only, not recent |
| **Performance Degradation** | Medium | Medium | Circuit breakers, graceful degradation |

## Implementation Tickets

### WAL-601: Position Tracking Data Model (3h)
**⚠️ Implementation gated on GPT-action note in place (docs/future-gpt-action.md)**

**Acceptance Criteria:**
- [ ] Create Position and PositionPnL dataclasses
- [ ] Add position fields to Trade model
- [ ] Database schema migration for position storage
- [ ] Unit tests for data models

### WAL-602: Cost Basis Calculator (4h)
**Acceptance Criteria:**
- [ ] Implement FIFO cost basis calculation
- [ ] Implement weighted average calculation
- [ ] Handle edge cases (airdrops, dust)
- [ ] Property-based tests with hypothesis

### WAL-603: Position Builder Service (4h)
**Acceptance Criteria:**
- [ ] Build positions from trade history
- [ ] Track balance changes per token
- [ ] Identify open vs closed positions
- [ ] Integration tests with real trade data

### WAL-604: Unrealized P&L Calculator (3h)
**Acceptance Criteria:**
- [ ] Calculate unrealized P&L for positions
- [ ] Integrate with market cap service for prices
- [ ] Add confidence scoring for price age
- [ ] Accuracy tests vs manual calculations

### WAL-605: Position Cache Layer (3h)
**Acceptance Criteria:**
- [ ] Redis cache for positions with TTL
- [ ] Cache invalidation on new trades
- [ ] Fallback to calculation if cache miss
- [ ] Performance benchmarks < 100ms

### WAL-606: API Endpoint Enhancement (4h)
**Acceptance Criteria:**
- [ ] Add positions array to /v4/analyze response
- [ ] Include realized + unrealized P&L totals
- [ ] Add /v4/positions/{wallet} endpoint
- [ ] OpenAPI documentation updates

### WAL-607: SSE Position Streaming (4h)
**Acceptance Criteria:**
- [ ] Emit position updates via SSE
- [ ] 30-second update interval
- [ ] Delta updates only (changed positions)
- [ ] Client example code

### WAL-608: Balance Verification Service (3h)
**Acceptance Criteria:**
- [ ] RPC calls to verify on-chain balances
- [ ] Reconciliation with calculated positions
- [ ] Alert on mismatches > 0.1%
- [ ] Monitoring dashboard

### WAL-609: Edge Case Handlers (4h)
**Acceptance Criteria:**
- [ ] Airdrop detection and handling
- [ ] Token migration mapping system
- [ ] Dust threshold configuration
- [ ] MEV sandwich detection

### WAL-610: Performance & Accuracy Testing (4h)
**Acceptance Criteria:**
- [ ] Load tests with 10k trade wallets
- [ ] Accuracy validation on 20 real wallets
- [ ] Memory profiling under load
- [ ] Performance regression tests

## Rollback Plan

Feature flags for gradual rollout:
```python
FEATURE_FLAGS = {
    "positions_enabled": False,          # Master switch
    "unrealized_pnl_enabled": False,     # Enable unrealized P&L
    "streaming_positions": False,        # SSE position updates
    "balance_verification": False,       # On-chain verification
    "cost_basis_method": "weighted_avg"  # or "fifo"
}
```

Rollback procedure:
1. Set `positions_enabled = False`
2. API returns v3 response format
3. No position calculations performed
4. Cache entries expire naturally

## Review Checklist

| Item | Status |
|------|--------|
| All data fields enumerated | ✅ |
| Algorithm covers every edge-case row | ✅ |
| Accuracy target justified | ✅ |
| Rollback / feature flag path | ✅ |
| Unit + integration test plan | ✅ |
| Perf impact estimate | ✅ |

## Summary

P6 extends WalletDoctor with comprehensive position tracking and unrealized P&L calculation. The design prioritizes accuracy, performance, and graceful handling of edge cases while maintaining backward compatibility through feature flags. 