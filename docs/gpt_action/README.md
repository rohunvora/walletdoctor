# WalletDoctor GPT Action Integration Guide

## Overview

This guide provides everything needed to integrate WalletDoctor's portfolio API into a CustomGPT, enabling it to answer questions about Solana wallet portfolios and P&L in real-time.

## OpenAPI Schema Notes

- **walletdoctor_action_clean.json**: The cleaned OpenAPI 3.1.0 spec optimized for ChatGPT Actions
  - Uses OpenAPI 3.1.0 (required by ChatGPT)
  - Single production server only (localhost removed to avoid "multiple hostnames" warning)
  - Nullable fields properly marked
  - Clean JSON formatting

- **walletdoctor_action.json**: Original spec with both production and development servers (OpenAPI 3.0.1)

## Quick Start

### 1. Import the Action

In your CustomGPT configuration:
1. Go to **Actions** → **Create new action**
2. Import schema from: `https://walletdoctor.app/docs/gpt_action/walletdoctor_action.yaml`
3. Or paste the schema from [walletdoctor_action.yaml](./walletdoctor_action.yaml)

### 2. Configure Authentication

Add your API key to the Authentication section:
- **Type**: API Key
- **Header name**: X-Api-Key
- **API Key**: `wd_YOUR_32_CHARACTER_KEY_HERE`

### 3. Test the Connection

Use the test feature with wallet: `3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2`

## API Endpoint

### Get Wallet Portfolio
```
GET /v4/positions/export-gpt/{wallet}
```

**Parameters:**
- `wallet` (path, required): Solana wallet address
- `schema_version` (query, optional): Schema version (default: "1.1")

**Headers:**
- `X-Api-Key`: Your API key in format `wd_<32-characters>`

## Example Requests

### cURL
```bash
curl -X GET "https://walletdoctor.app/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2" \
  -H "X-Api-Key: wd_12345678901234567890123456789012" \
  -H "Accept: application/json"
```

### Postman

1. **Method**: GET
2. **URL**: `https://walletdoctor.app/v4/positions/export-gpt/{{wallet}}`
3. **Headers**:
   - `X-Api-Key`: `{{api_key}}`
   - `Accept`: `application/json`
4. **Variables**:
   - `wallet`: `3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2`
   - `api_key`: `wd_YOUR_KEY_HERE`

[![Run in Postman](https://run.pstmn.io/button.svg)](https://god.gw.postman.com/run-collection/YOUR_COLLECTION_ID)

### Python
```python
import requests

wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
api_key = "wd_12345678901234567890123456789012"

response = requests.get(
    f"https://walletdoctor.app/v4/positions/export-gpt/{wallet}",
    headers={"X-Api-Key": api_key}
)

portfolio = response.json()
print(f"Total P&L: ${portfolio['summary']['total_unrealized_pnl_usd']}")
```

## Example Response

### Success (200 OK)
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
    },
    {
      "position_id": "3JoVBi:EPjFW:1706352000",
      "token_symbol": "WIF",
      "token_mint": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
      "balance": "500.25",
      "decimals": 6,
      "cost_basis_usd": "1000.00",
      "current_price_usd": "2.50",
      "current_value_usd": "1250.63",
      "unrealized_pnl_usd": "250.63",
      "unrealized_pnl_pct": "25.06",
      "price_confidence": "high",
      "price_age_seconds": 12,
      "opened_at": "2024-01-26T12:00:00Z",
      "last_trade_at": "2024-01-28T08:00:00Z"
    }
  ],
  "summary": {
    "total_positions": 2,
    "total_value_usd": "1282.13",
    "total_unrealized_pnl_usd": "256.63",
    "total_unrealized_pnl_pct": "25.02",
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

### Stale Cache Response
When data is served from cache and is stale:
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

## GPT Prompt Examples

### Basic Portfolio Query
**User**: "What's my current portfolio?"

**GPT should call**: `getWalletPortfolio` with the user's wallet address

**GPT Response**: 
> Your portfolio contains 2 positions worth $1,282.13 total:
> - BONK: 1,000,000 tokens worth $31.50 (+23.53% / +$6.00)
> - WIF: 500.25 tokens worth $1,250.63 (+25.06% / +$250.63)
> 
> Total unrealized profit: +$256.63 (+25.02%)

### Detailed P&L Analysis
**User**: "Show me my winners and losers"

**GPT Response**:
> Based on your current positions:
>
> **Winners:**
> - WIF: +$250.63 (+25.06%) - Your best performer
> - BONK: +$6.00 (+23.53%) - Solid gains
>
> **Losers:**
> None - all positions are in profit!
>
> Your portfolio is up 25.02% overall.

### Price Staleness Handling
When `stale: true` is present:

**GPT Response**:
> ⚠️ Note: This data is from cached results (20 minutes old). Prices may have changed. 
>
> Based on the last update, your portfolio shows...

## Error Handling

### 401 Unauthorized
```json
{
  "error": "API key required",
  "message": "Please provide API key via X-Api-Key header"
}
```
**GPT should say**: "I need authentication to access wallet data. Please configure your API key."

### 404 Not Found
```json
{
  "error": "Wallet not found",
  "message": "No trading data found for wallet ADDRESS"
}
```
**GPT should say**: "I couldn't find any trading data for this wallet address."

## Data Considerations

### Precision
- All monetary values are strings to preserve decimal precision
- GPT should parse these as decimal numbers for calculations
- Display with appropriate decimal places (usually 2 for USD)

### Price Confidence
- `high`: Direct AMM/DEX price, <60s old
- `est`: Secondary source or 60s-5min old  
- `stale`: >5 minutes old

### Null Handling
- Missing optional fields are omitted (not null)
- GPT should check field existence before use
- Zero values are explicit: "0.00" not null

## Performance

- **Cached data**: <200ms response time
- **Fresh fetch**: <1.5s response time
- **Rate limits**: 50 requests/minute per API key

## Integration Tips

1. **Cache Awareness**: Check `stale` flag and inform users when data might be outdated

2. **Error Messages**: Provide user-friendly messages for API errors

3. **Number Formatting**: Parse string numbers and format appropriately:
   ```
   $1,234.56 (not $1234.5600000)
   +25.02% (not +25.0234234%)
   ```

4. **Position Grouping**: Consider grouping by profit/loss or token type

5. **Summary First**: Lead with the summary before listing individual positions

## Support

- **Documentation**: https://walletdoctor.app/docs
- **API Status**: https://status.walletdoctor.app
- **Support Email**: support@walletdoctor.app

## Schema Updates

The current schema version is 1.1. Future versions will be backward compatible. Always check the `schema_version` field in responses. 