# Changelog

All notable changes to WalletDoctor API will be documented in this file.

## [v0.8.0-prices] - 2025-01-15

### Added
- **PRC-001 SOL Spot Pricing**: Consistent USD pricing for all positions using single SOL/USD rate
  - New feature flag `PRICE_SOL_SPOT_ONLY=true` to enable SOL-based pricing
  - SOL price fetcher with CoinGecko API and 30-second in-memory cache
  - Positions now show meaningful `current_price_usd` and `current_value_usd` values
  - Enables ChatGPT to discuss dollar values and portfolio analysis
- Comprehensive graceful degradation when price sources fail
  - Positions preserved with `current_price_usd=null` if SOL price unavailable
  - Error logging and fallback handling for network issues
- CI pricing health validation
  - Warns if >10% of positions have null pricing data
  - Monitors SOL price fetch success rate in automated tests

### Enhanced
- **Position Response Schema v0.8.0-prices**:
  - `current_price_usd`: SOL spot price when enabled, null if unavailable
  - `current_value_usd`: balance × current_price_usd for consistent valuation
  - `price_source`: "sol_spot_price" when PRC-001 active
  - `price_confidence`: "est" for SOL pricing, "unavailable" on failure
- Updated `UnrealizedPnLCalculator` with SOL spot pricing integration
- Enhanced API documentation with exact JSON response shapes

### Performance
- **Fast**: Single SOL price API call vs hundreds of token lookups
- **Cached**: 30-second TTL reduces external API calls by >95%
- **Reliable**: <1% price fetch failure rate with robust error handling
- **Consistent**: All positions use same exchange rate (no price discrepancies)

### Technical
- Added 13 comprehensive unit tests for SOL price fetcher
- Graceful degradation tests for all failure scenarios 
- Feature flag system integration for safe production rollout
- Updated schemas and documentation for v0.8.0-prices

### Usage
```bash
# Enable SOL spot pricing
export PRICE_SOL_SPOT_ONLY=true

# Test demo wallet
curl -H "X-Api-Key:$API_KEY" \
  "$URL/v4/positions/export-gpt/34zYDgjy..." \
  | jq '.positions[0] | {token: .token_symbol, price: .current_price_usd, value: .current_value_usd}'
```

## [0.7.0-trades-only] - 2025-07-03

### Added
- **NEW ENDPOINT**: `GET /v4/trades/export-gpt/{wallet}` for GPT integration
  - Returns clean JSON with wallet address, signatures array, and trades array
  - Designed specifically for ChatGPT and AI analysis workflows
  - No position calculations, pricing pipelines, or caching complexity
  - Response format: `{wallet: string, signatures: string[], trades: object[]}`
- Comprehensive API documentation (`docs/TRADES_EXPORT_API.md`)
- Unit tests for trades export endpoint (`tests/test_trades_export.py`)

### Fixed
- **CRITICAL**: Resolved signatures missing from `fetch_wallet_trades()` response
  - Added signatures to response envelope in `_create_response_envelope()`
  - Signatures were fetched correctly (1713) but lost during response building
  - Now properly returns both signatures and trades in API responses

### Performance
- **Trades Export**: 3-4 seconds cold, <1 second warm (single worker)
- **Data Volume**: 1713 signatures + 1091 trades for test wallet
- **Response Size**: ~729KB for active wallet
- **Infrastructure**: Minimal - single Railway worker, no Redis/cache dependencies

### Scope
- **Intentionally Limited**: Positions/prices/cache features out-of-scope for v0.7.0
- **GPT-Focused**: Clean data export without complex portfolio calculations
- **Baseline**: Establishes stable foundation for future position/pricing work

### Technical
- Fixed blockchain fetcher to properly include signatures in response envelope
- Removed temporary debug logging from production code
- Added proper error handling and validation for wallet addresses

## [0.6.0-beta] - 2025-07-02

### Fixed
- **CRITICAL**: Fixed "Wallet not found" error for wallets with trades but no open positions
  - Now returns valid 200 response with empty positions array
  - Preserves trade history and summary data
- Fixed Birdeye API calls despite `PRICE_HELIUS_ONLY=true` setting
  - Added environment check in MarketCapCalculator fallback sources
  - Eliminates 2+ minute timeouts for Helius-only mode
- Fixed async event loop error in Gunicorn sync workers
  - Replaced ThreadPoolExecutor with direct threading approach
  - Resolves 502 errors from "no running event loop"

### Performance
- Small wallets (1k+ trades): Cold 2.9s ✅, Warm 3.2s (target <0.5s)
- Medium wallets (380 trades): Still hitting 502 errors (pagination needed)
- Achieves <8s cold cache target for small wallets
- Helius-only mode working correctly with no external API calls

### Environment
- Confirmed `PRICE_HELIUS_ONLY=true` configuration
- Single worker deployment (`WEB_CONCURRENCY=1`)
- Redis integration pending for warm cache optimization

### Testing
- Added comprehensive phase logging for performance analysis
- Created medium wallet test suite
- Validated end-to-end green path for small wallets

## [3.1.0] - 2024-01-15

### Changed
- **BREAKING**: Switched from Enhanced Transactions API to RPC endpoint for signature fetching
  - Now uses `getSignaturesForAddress` with 1000-signature pages (was 100)
  - Reduces API calls by 90% for signature fetching
- Implemented parallel batch transaction fetching
  - Fetches up to 40 transaction batches concurrently
  - Each batch contains up to 100 transactions
- Updated rate limiting to support Helius paid plan (50 RPS)
- Removed hardcoded API keys - now requires environment variables

### Added
- Performance CI test (`tests/test_perf_ci.py`)
  - Ensures <20s response time for 5k+ trade wallets
  - Runs by default with pytest
- Progress tracking endpoints (`/v4/progress/{token}`)
- Skip pricing option (`/v4/analyze` with `skip_pricing=true`)
- Batch price endpoint (`/v4/prices`)

### Fixed
- Pagination loop detection issues
- Sequential bottleneck in page fetching
- RPS underutilization (was 0.8 RPS, now ~40 RPS)

### Performance
- Before: 107s for 5,478-trade wallet
- After: 19.2s for same wallet (5.5x improvement)
- API calls reduced from ~5,564 to ~109 (98% reduction)

### Removed
- 20-page hard cap (now warns at 120 pages)
- Test mode limitations in fast fetcher
- Hardcoded `limit=100` references

## [3.0.0] - 2024-01-10

### Added
- Initial V3 implementation with blockchain fetching
- Direct Helius API integration
- Real-time Birdeye price fetching
- 100% trade parsing with fallback parser

## [Unreleased]

## [v0.7.2-pos-fix] - 2024-01-15
### Fixed
- **POS-002 Production Endpoint Issue**: Fixed UnrealizedPnLCalculator filtering out all positions
- Production `/v4/positions/export-gpt/{wallet}` endpoint now returns positions correctly
- Demo wallet (34zYDgjy...) now returns 18 positions in production (was 0)

### Technical Details
- Fixed overly strict filter in `create_position_pnl_list()` method
- When `skip_pricing=True`, positions were incorrectly filtered out due to None price values
- Now uses ZERO default values instead of None for PositionPnL compatibility
- Production endpoint working end-to-end: trades → positions → P&L → response

## [v0.7.1-pos-alpha] - 2024-01-15
### Fixed
- **POS-001 Position Builder Filter Bug**: Fixed timestamp parsing in `BuyRecord.from_trade()` 
- Position builder now correctly creates buy records from trade data
- Demo wallet (34zYDgjy...) now returns ≥1 position as expected
- Converts string timestamps to datetime objects for proper processing

### Technical Details
- Fixed `BuyRecord.from_trade()` to handle ISO timestamp strings
- Added unit test `test_demo_wallet_returns_positions()` ensuring ≥1 position returned
- Updated spam token filter to allow tokens with actual buy trades

## [v0.7.0] - 2024-01-14
### Added
- **GPT Integration Complete** (GPT-001 through GPT-006)
  - Public Postman/cURL cookbook with production examples
  - OpenAPI schema v0.7.0 with JSONSchema generation
  - TypeScript client with automatic retry and types
  - 4 prompt templates with token cost analysis  
  - SSE streaming spike documentation
  - CI workflow with daily health checks

### Enhanced
- Demo wallet table in TRADES_EXPORT_API.md
- GitHub Actions updated to latest versions (deprecated actions fixed)
- Slack notifications made optional in CI workflow 