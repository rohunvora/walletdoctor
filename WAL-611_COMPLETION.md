# WAL-611: Export-for-GPT Endpoint - COMPLETED ✅

## Summary
Implemented a read-only GPT export endpoint that serves position data in schema v1.1 JSON format, enabling GPTs to answer "What's my portfolio & P/L right now?" without extra calls.

## Implementation Details

### 1. New Endpoint: GET /v4/positions/export-gpt/{wallet}
- **File**: `src/api/wallet_analytics_api_v4_gpt.py`
- **Authentication**: Simple API key via `X-Api-Key` header
- **Query Params**: `schema_version` (default: 1.1)
- **Performance**: <200ms cached, <1.5s cold fetch

### 2. GPT Schema v1.1 Format
Based on `docs/future-gpt-action.md` specification:
```json
{
  "schema_version": "1.1",
  "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
  "timestamp": "2024-01-28T10:30:00Z",
  "positions": [
    {
      "position_id": "3JoVBi:DezXAZ:1706438400",
      "token_symbol": "BONK",
      "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
      "balance": "1000000.123456",
      "decimals": 5,
      "cost_basis_usd": "25.50",
      "current_price_usd": "0.0000315",
      "current_value_usd": "31.50",
      "unrealized_pnl_usd": "6.00",
      "unrealized_pnl_pct": "23.53",
      "price_confidence": "high",
      "price_age_seconds": 45,
      "opened_at": "2024-01-27T15:30:00Z",
      "last_trade_at": "2024-01-28T09:15:00Z"
    }
  ],
  "summary": {
    "total_positions": 1,
    "total_value_usd": "31.50",
    "total_unrealized_pnl_usd": "6.00",
    "total_unrealized_pnl_pct": "23.53",
    "stale_price_count": 0
  },
  "price_sources": {
    "primary": "https://walletdoctor.app/v4/prices",
    "primary_hint": "POST {mints: [string], timestamps: [number]} returns {mint: price_usd} in JSON",
    "fallback": "https://api.coingecko.com/api/v3/simple/price",
    "fallback_hint": "GET ?ids={coingecko_id}&vs_currencies=usd returns {id: {usd: price}} in JSON"
  }
}
```

### 3. Staleness Support
- When data is from cache and stale, response includes:
  - `"stale": true`
  - `"age_seconds": 1200` (example)
- Reuses position cache with automatic refresh triggers

### 4. Authentication
- Simple API key format: `wd_<32-characters>` (35 chars total)
- Header: `X-Api-Key`
- Validates format, logs access
- Production-ready for database validation

### 5. Performance Headers
- `X-Response-Time-Ms`: Request duration
- `X-Cache-Status`: HIT (stale) or MISS (fresh)

## Testing

### Unit Tests: `tests/test_gpt_export_api.py`
✅ 12 tests, all passing:
- Authentication (no auth, invalid key)
- Valid wallet with fresh/stale data
- Wallet not found
- Schema formatting
- Performance requirements
- Health and home endpoints

### Test Results
```
tests/test_gpt_export_api.py::TestGPTExportAPI::test_no_auth PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_invalid_api_key_format PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_invalid_wallet_address PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_unsupported_schema_version PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_valid_wallet_fresh_data PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_valid_wallet_stale_data PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_wallet_not_found PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_positions_disabled PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_schema_formatting PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_performance_requirements PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_health_endpoint PASSED
tests/test_gpt_export_api.py::TestGPTExportAPI::test_home_endpoint PASSED
```

## Files Changed
1. **src/api/wallet_analytics_api_v4_gpt.py** - New GPT export API (357 lines)
2. **tests/test_gpt_export_api.py** - Comprehensive test suite (359 lines)

## Usage Example

### Request
```bash
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  https://walletdoctor.app/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2
```

### Response (Cached, Fresh)
```json
{
  "schema_version": "1.1",
  "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
  "timestamp": "2024-01-28T10:30:00Z",
  "positions": [...],
  "summary": {
    "total_positions": 5,
    "total_value_usd": "1250.75",
    "total_unrealized_pnl_usd": "325.40",
    "total_unrealized_pnl_pct": "35.15",
    "stale_price_count": 0
  },
  "price_sources": {...}
}
```

### Response (Cached, Stale)
```json
{
  "schema_version": "1.1",
  "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
  "timestamp": "2024-01-28T10:30:00Z",
  "stale": true,
  "age_seconds": 1234,
  "positions": [...],
  "summary": {...},
  "price_sources": {...}
}
```

## Next Steps
- WAL-612: Create GPT Action manifest & examples
- WAL-613: Build round-trip validation harness

## Notes
- Endpoint runs on port 8081 in development
- Reuses existing position cache infrastructure (WAL-607)
- All monetary values as strings to preserve precision
- Price confidence mapped: high→high, est→est, others→stale 