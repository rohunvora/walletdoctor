# WAL-604: Unrealized P&L Calculator - COMPLETED ✅

## Summary
Implemented the Unrealized P&L Calculator that integrates with the market cap service to fetch current prices and calculate unrealized gains/losses for open positions with confidence scoring.

## What Was Built

### 1. Core Components

#### `UnrealizedPnLResult` dataclass
- Holds calculation results including price, value, P&L, and confidence
- Tracks price source and last update time
- Includes error field for failed calculations

#### `UnrealizedPnLCalculator` class
Main service with the following methods:
- `calculate_unrealized_pnl()`: Single position P&L calculation
- `calculate_batch_unrealized_pnl()`: Batch processing with concurrency control
- `calculate_portfolio_unrealized_pnl()`: Portfolio-level aggregation
- `create_position_pnl_list()`: Converts positions to PositionPnL objects
- Internal helpers for price fetching and confidence scoring

### 2. Key Features

#### Market Cap Integration
- Seamlessly integrates with existing `MarketCapCalculator`
- Extracts price data from market cap results
- Handles unavailable prices gracefully

#### Confidence Scoring
- Converts MC service confidence levels to price confidence
- Degrades confidence based on price age:
  - < 60s: Maintains original confidence
  - 60s-5min: Degrades HIGH → ESTIMATED
  - > 5min: Degrades to STALE
- Human-readable age labels (fresh, recent, stale, very stale)

#### Batch Processing
- Processes positions in configurable batches (default 20)
- Concurrent execution with asyncio.gather
- Handles exceptions per position without failing entire batch

#### Special Cases
- Airdrop positions (zero cost basis) = 100% gain
- Missing prices handled with error results
- Feature flag integration for gradual rollout

### 3. Performance Optimizations
- Batch API calls to prevent rate limiting
- Concurrent processing within batches
- Optional price parameter to skip fetching

### 4. Accuracy Features
- Decimal type for all calculations
- Proper percentage calculation with edge cases
- Confidence tracking for data quality

## Test Coverage

### Unit Tests (16 tests, all passing)
- Price gain/loss calculations ✅
- Provided vs fetched prices ✅
- Unavailable prices handling ✅
- Feature flag disabled behavior ✅
- Airdrop positions (zero cost) ✅
- Batch calculations ✅
- Confidence conversion logic ✅
- Portfolio aggregation ✅
- Price age labeling ✅
- Error handling ✅

### Integration Test
Created comprehensive integration test demonstrating:
- Full workflow from trades → positions → unrealized P&L
- Multiple tokens (BONK, WIF) with different price movements
- Portfolio summary calculation
- Combined realized + unrealized P&L tracking

Example output:
```
📊 Built 2 open positions:
  - BONK: 1300000 tokens, cost basis $900.00
  - WIF: 100000 tokens, cost basis $1000.00

💰 Unrealized P&L Results:
  - BONK:
    Current value: $2600.000
    Unrealized P&L: $1700.000 (188.9%)
    Price confidence: high
  - WIF:
    Current value: $800.000
    Unrealized P&L: $-200.000 (-20.0%)
    Price confidence: high

📈 Portfolio Summary:
  Total cost basis: $1,900.00
  Total current value: $3,400.00
  Total unrealized P&L: $1,500.00
  Total unrealized P&L %: 78.95%
```

## API Integration

The calculator is designed to integrate with the V4 API endpoint:

```python
# Example API usage
positions = position_builder.build_positions_from_trades(trades, wallet)
pnl_calculator = UnrealizedPnLCalculator()
pnl_results = await pnl_calculator.create_position_pnl_list(positions)

# Add to API response
response["positions"] = [pnl.to_dict() for pnl in pnl_results]
response["unrealized_pnl_total"] = sum(p.unrealized_pnl_usd for p in pnl_results)
```

## Configuration

### Feature Flags
- `should_calculate_unrealized_pnl()`: Master control for P&L calculation
- Returns error result when disabled

### Constants
```python
PRICE_FRESH_SECONDS = 60      # < 1 minute
PRICE_RECENT_SECONDS = 300    # < 5 minutes  
PRICE_STALE_SECONDS = 900     # < 15 minutes
DEFAULT_BATCH_SIZE = 20
```

## Next Steps
- WAL-605: Position Cache Layer (Redis caching)
- WAL-606: API Endpoint Enhancement (integrate with V4)
- WAL-607: SSE Position Streaming (real-time updates)

## Files Created/Modified
- `src/lib/unrealized_pnl_calculator.py` - Main implementation
- `tests/test_unrealized_pnl_calculator.py` - Unit tests
- `tests/test_unrealized_pnl_integration.py` - Integration test
- `src/lib/position_models.py` - Fixed datetime timezone issues

## Key Decisions
1. **Decimal precision**: All calculations use Python Decimal for accuracy
2. **Confidence degradation**: Time-based degradation ensures fresh data
3. **Batch processing**: Prevents API rate limiting while maintaining performance
4. **Error handling**: Individual position errors don't fail entire batch
5. **Feature flags**: Safe rollout with ability to disable

## Dependencies
- Existing market cap service (P5)
- Position models from WAL-601
- Position builder from WAL-603

## Status
✅ Complete - Unrealized P&L calculator with market cap integration and confidence scoring 