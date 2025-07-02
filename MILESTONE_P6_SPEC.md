# WalletDoctor P6: Unrealized P&L & Open Position Tracking

## Goal
Add real-time unrealized P&L tracking and open position management to the WalletDoctor API, enabling users to see both realized and paper gains/losses for their current holdings.

## High-level Flow

1. **Position Detection**: During trade processing, identify which tokens are currently held (open positions)
2. **Current Price Fetch**: Get real-time prices for all open positions via the existing MC calculator
3. **Unrealized P&L Calc**: Compare average entry price to current price for each position
4. **Position Summary**: Aggregate both realized and unrealized P&L for complete portfolio view
5. **Stream Updates**: Include position data in the SSE stream for real-time monitoring

## WAL-6xx Ticket Grid

| Ticket | Title | Description | Acceptance Criteria |
|--------|-------|-------------|---------------------|
| WAL-601 | Position Tracker | Create position tracking service that maintains open positions from trade history | - `PositionTracker` class with add/reduce/close methods<br>- Track average entry price, quantity, cost basis<br>- Handle partial sells correctly<br>- Unit tests with 95% coverage |
| WAL-602 | Entry Price Calculator | Calculate weighted average entry prices for positions with multiple buys | - FIFO/LIFO/Average cost methods<br>- Handle SOL and USDC denominated trades<br>- Account for fees in cost basis<br>- Tests for complex position scenarios |
| WAL-603 | Unrealized P&L Engine | Calculate unrealized gains/losses using current market prices | - Fetch current prices via MC calculator<br>- Calculate USD and percentage gains<br>- Handle positions without current price data<br>- Return confidence levels for prices |
| WAL-604 | Position Enrichment | Add position data to wallet analytics response | - New `positions` array in API response<br>- Include: token, quantity, avg_price, current_price, unrealized_pnl<br>- Sort by value or P&L percentage<br>- Maintain backward compatibility |
| WAL-605 | Summary Stats Update | Update summary statistics to include unrealized P&L | - Add `unrealized_pnl`, `total_pnl` fields<br>- Update win rate to include paper gains<br>- Add `open_positions_count`<br>- Show portfolio current value |
| WAL-606 | Stream Position Updates | Include position updates in SSE stream | - Emit position events during processing<br>- Show when positions open/close<br>- Update unrealized P&L periodically<br>- Throttle updates appropriately |
| WAL-607 | Position Cache Layer | Cache position calculations for performance | - Cache position state by wallet<br>- Invalidate on new trades<br>- TTL for current price data<br>- Redis integration with fallback |
| WAL-608 | Historical Position API | New endpoint for position history at any point in time | - `/api/v1/positions/{wallet}?timestamp=`<br>- Show positions held at timestamp<br>- Calculate historical unrealized P&L<br>- Support date ranges |
| WAL-609 | Position Export | Export positions to CSV/JSON with cost basis | - Include all tax-relevant fields<br>- Support multiple cost basis methods<br>- Add acquisition dates<br>- Format for tax software |
| WAL-610 | Integration Tests | End-to-end tests for position tracking | - Test wallet with 50+ trades<br>- Verify position calculations<br>- Check edge cases (dust, fees)<br>- Performance benchmarks |

## Risk Factors

1. **Performance Impact**: Fetching current prices for many positions could slow down API response
   - *Mitigation*: Aggressive caching, parallel price fetches, optional position data
   
2. **Price Accuracy**: Current prices might not reflect actual liquidation value for illiquid tokens
   - *Mitigation*: Include liquidity/confidence indicators, show last trade time
   
3. **Complex Position History**: Tokens with many small trades can create complex position tracking
   - *Mitigation*: Position consolidation logic, dust threshold settings
   
4. **Memory Usage**: Tracking all positions in memory could be expensive for active wallets
   - *Mitigation*: Pagination, position archival for closed positions

## Success Metrics

- **Response Time**: < 500ms additional latency for position data
- **Price Coverage**: > 90% of open positions have current prices
- **Accuracy**: Position calculations match manual verification 100%
- **Cache Hit Rate**: > 80% for position data requests
- **User Adoption**: 50% of API calls include position data within 2 weeks

## Technical Considerations

### Position State Model
```python
@dataclass
class Position:
    token_mint: str
    symbol: str
    quantity: Decimal
    avg_entry_price: Decimal
    total_cost_basis: Decimal
    realized_pnl: Decimal
    current_price: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    last_updated: datetime
    confidence: str
```

### API Response Enhancement
```json
{
  "summary": {
    "realized_pnl": 420.69,
    "unrealized_pnl": 156.32,
    "total_pnl": 577.01,
    "open_positions_count": 8,
    "portfolio_value": 2834.45
  },
  "positions": [
    {
      "token_mint": "...",
      "symbol": "BONK",
      "quantity": 1000000,
      "avg_entry_price": 0.0000234,
      "current_price": 0.0000456,
      "cost_basis": 23.40,
      "current_value": 45.60,
      "unrealized_pnl": 22.20,
      "unrealized_pnl_pct": 94.87,
      "confidence": "high"
    }
  ]
}
```

## Alternative Approach: UI/SDK Focus

If you prefer to prioritize developer experience over features:

1. **React Trading Dashboard**: Beautiful web UI for wallet analysis
2. **TypeScript SDK**: Type-safe client library with position tracking
3. **WebSocket Client**: Real-time position updates via WebSocket
4. **Mobile SDK**: React Native components for mobile apps
5. **Webhook System**: Push notifications for position changes

Let me know which direction you'd prefer for P6! 