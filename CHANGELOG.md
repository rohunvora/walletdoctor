# Changelog

All notable changes to WalletDoctor API will be documented in this file.

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