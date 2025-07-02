# Future GPT Action Integration for P6 Position Data

## Overview
This note outlines how P6's position tracking data will be exposed to CustomGPT Actions, ensuring our data model design remains compatible with future GPT integration needs.

## Minimal JSON Schema for GPT Action

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
    "total_positions": 3,
    "total_value_usd": "1250.75",
    "total_unrealized_pnl_usd": "325.40",
    "total_unrealized_pnl_pct": "35.15",
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

## Data Source Mapping

| GPT Field | P6 Source | Notes |
|-----------|-----------|-------|
| `position_id` | `Position.position_id` | Unique identifier for each position session |
| `balance` | `Position.balance` | String to preserve precision |
| `decimals` | `TokenMetadata.decimals` | Integer for proper scaling |
| `cost_basis_usd` | `Position.cost_basis_usd` | String for decimal accuracy |
| `current_price_usd` | `PositionPnL.current_price_usd` | From market cap service |
| `unrealized_pnl_*` | `PositionPnL.unrealized_pnl_*` | Calculated in real-time |
| `price_confidence` | `PositionPnL.price_confidence` | "high", "est", "stale" |
| `price_age_seconds` | `now() - PositionPnL.last_price_update` | For freshness check |

## Fields Requiring Special Handling

### 1. **Decimal Precision**
- **Issue**: JSON doesn't support Decimal type, float loses precision
- **Solution**: Serialize all monetary values as strings
- **GPT Impact**: GPT must parse strings for calculations

### 2. **Large Token Balances**
- **Issue**: Some tokens have 18 decimals (e.g., "1234567890123456789")
- **Solution**: Keep as string, provide decimal places separately if needed
- **GPT Impact**: GPT needs to handle scientific notation conversions

### 3. **Timestamp Formats**
- **Issue**: Various timestamp formats can confuse GPT
- **Solution**: Always use ISO 8601 (RFC 3339) format
- **GPT Impact**: Consistent parsing, timezone-aware

### 4. **Null/Missing Values**
- **Issue**: GPT may misinterpret null vs 0 vs missing
- **Solution**: Explicit `null` for unknown, omit field if not applicable
- **GPT Impact**: Clear prompt instructions needed for null handling

## Implementation Approach

```python
# In Position Service (WAL-603)
async def export_for_gpt(wallet: str) -> Dict:
    """Export positions in GPT-friendly format"""
    positions = await self.get_positions(wallet)
    
    return {
        "schema_version": "1.1",
        "wallet": wallet,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "positions": [
            {
                "position_id": p.position_id,
                "balance": str(p.balance),  # Decimal → string
                "decimals": p.token_metadata.decimals,  # For proper scaling
                "cost_basis_usd": str(p.cost_basis_usd),
                # ... other fields
            }
            for p in positions
        ],
        "summary": self._calculate_summary(positions),
        "price_sources": {
            "primary": f"{API_BASE}/v4/prices",
            "primary_hint": "POST {mints: [string], timestamps: [number]} returns {mint: price_usd} in JSON",
            "fallback": "https://api.coingecko.com/api/v3/simple/price",
            "fallback_hint": "GET ?ids={coingecko_id}&vs_currencies=usd returns {id: {usd: price}} in JSON"
        }
    }
```

## Potential GPT Limitations to Consider

1. **Calculation Accuracy**: GPT may introduce rounding errors in complex calculations
2. **Rate Limiting**: GPT making direct price API calls could hit limits
3. **Context Window**: Large portfolios (>100 positions) may exceed token limits
4. **Consistency**: GPT responses may vary for identical inputs

## Recommendations

1. Keep monetary values as strings to preserve precision
2. Include pre-calculated summary stats to reduce GPT computation needs
3. Provide both token mint and symbol for flexible lookups
4. Add price source URLs for GPT to fetch updates if needed
5. Version the schema (add `"schema_version": "1.0"`) for future changes

This design ensures P6 data structures can be cleanly serialized for GPT consumption without loss of precision or functionality. 