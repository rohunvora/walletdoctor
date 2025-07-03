# Changelog

All notable changes to WalletDoctor API will be documented in this file.

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