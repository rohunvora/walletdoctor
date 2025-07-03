# Trades Export API Documentation

## Overview

The WalletDoctor GPT Export API provides a simplified endpoint for exporting raw trade data and transaction signatures for AI analysis. This endpoint is designed for ChatGPT and other AI systems that need clean, structured access to wallet trading history.

## Endpoint

### `GET /v4/trades/export-gpt/{wallet_address}`

Export raw signatures and trades data for GPT integration.

#### Parameters

- **wallet_address** (path, required): Solana wallet address to analyze
  - Format: Base58-encoded public key
  - Example: `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`

#### Headers

- **X-Api-Key** (required): API authentication key
  - Format: `wd_` followed by 32 alphanumeric characters
  - Example: `wd_12345678901234567890123456789012`

#### Response

- **Status**: 200 OK
- **Content-Type**: application/json

#### Response Schema (v0.7.0)

```json
{
  "wallet": "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
  "signatures": [
    "4NyzTh42S1bGswq8BNHvsm3PxM9NBYcmYgqk1n89HjiiKWHz2sT9Ut4rmuNHjeErTBAwoQV8aYP4oM54",
    "5m5bE9B5144pJwMsv9DA4L1ovc3r6mnJSosvEc22qjc59P9KcFtHvFbMXipeCV2mzsXMrbuyyJ9FG7TC34pWPNS7",
    "..."
  ],
  "trades": [
    {
      "action": "buy",
      "amount": 100.0,
      "dex": "RAYDIUM",
      "fees_usd": 0.05,
      "pnl_usd": 0.0,
      "position_closed": false,
      "price": 0.65,
      "priced": true,
      "signature": "4NyzTh42S1bGswq8BNHvsm3PxM9NBYcmYgqk1n89HjiiKWHz2sT9Ut4rmuNHjeErTBAwoQV8aYP4oM54",
      "timestamp": "2025-06-16T04:01:06",
      "token": "BONK",
      "token_in": {
        "amount": 1.5,
        "mint": "So11111111111111111111111111111111111111112",
        "symbol": "SOL"
      },
      "token_out": {
        "amount": 100.0,
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK"
      },
      "tx_type": "swap",
      "value_usd": 97.5
    },
    "..."
  ]
}
```

## Example Usage

### Base Configuration
- **Base URL**: `https://web-production-2bb2f.up.railway.app`
- **Authentication**: Required via `X-Api-Key` header
- **Rate Limits**: 50 requests per minute per API key

### cURL Example
```bash
curl -H "X-Api-Key: wd_your_api_key_here" \
     "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
```

### Python Example
```python
import requests

url = "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
headers = {"X-Api-Key": "wd_your_api_key_here"}

response = requests.get(url, headers=headers)
data = response.json()

print(f"Wallet: {data['wallet']}")
print(f"Signatures: {len(data['signatures'])}")
print(f"Trades: {len(data['trades'])}")
```

### JavaScript Example
```javascript
const wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya";
const apiKey = "wd_your_api_key_here";
const url = `https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/${wallet}`;

fetch(url, {
  headers: {
    'X-Api-Key': apiKey
  }
})
.then(response => response.json())
.then(data => {
  console.log(`Found ${data.signatures.length} signatures`);
  console.log(`Found ${data.trades.length} trades`);
  // Process the trades data
  data.trades.forEach(trade => {
    console.log(`${trade.action} ${trade.amount} ${trade.token} at ${trade.timestamp}`);
  });
});
```

## ChatGPT Integration

This endpoint is specifically designed for ChatGPT actions and analysis:

### Action Configuration
```yaml
openapi: "3.0.0"
info:
  title: "WalletDoctor Trades Export"
  version: "0.7.0"
servers:
  - url: "https://web-production-2bb2f.up.railway.app"
paths:
  /v4/trades/export-gpt/{wallet}:
    get:
      operationId: exportTrades
      summary: Export wallet trades and signatures
      parameters:
        - name: wallet
          in: path
          required: true
          schema:
            type: string
      security:
        - ApiKeyAuth: []
      responses:
        "200":
          description: Trade data exported successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  wallet:
                    type: string
                  signatures:
                    type: array
                    items:
                      type: string
                  trades:
                    type: array
                    items:
                      type: object
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-Api-Key
```

### Demo Wallets for Testing

Use these confirmed mainnet wallets for testing and development:

| Wallet Type | Address | Trades | Purpose |
|-------------|---------|--------|---------|
| Small Demo | `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya` | ≈1,100 | Quick testing, examples |
| Mid Demo | `AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8` | ≈2,300 | Performance testing |

These wallets are used in our CI system for daily health checks and provide reliable test data for GPT integration development.

### Sample Analysis Prompts
- "Analyze the trading patterns in this wallet data"
- "What are the most profitable trades in this data?"
- "Show me the token distribution and trading frequency"
- "Calculate the win rate and average position size"

## Performance Characteristics

- **Latency**: 3-4 seconds cold, <1 second warm
- **Data Size**: Typically 100KB-2MB depending on wallet activity
- **Caching**: Single worker, no Redis caching (minimal infrastructure)
- **Reliability**: Direct blockchain data, no intermediate processing

## Response Data Fields

### Signatures Array
- **Type**: Array of strings
- **Content**: Solana transaction signatures
- **Purpose**: Raw blockchain transaction references
- **Count**: Typically 1000-2000 for active wallets

### Trades Array
Each trade object contains:

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | Trade direction: "buy" or "sell" |
| `amount` | number | Token amount traded |
| `dex` | string | Exchange used (RAYDIUM, PUMP_AMM, etc.) |
| `fees_usd` | number | Transaction fees in USD |
| `pnl_usd` | number | Profit/loss for this trade |
| `signature` | string | Transaction signature |
| `timestamp` | string | ISO 8601 timestamp |
| `token` | string | Token symbol |
| `token_in` | object | Input token details |
| `token_out` | object | Output token details |
| `tx_type` | string | Transaction type (usually "swap") |
| `value_usd` | number | USD value of the trade |

## Error Responses

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Invalid wallet address | Wallet address format is incorrect |
| 401 | Unauthorized | Missing or invalid API key |
| 404 | Wallet not found | No trading data found for wallet |
| 429 | Rate limit exceeded | Too many requests |
| 500 | Internal server error | Server-side processing error |

## Scope and Limitations

### What This Endpoint Provides
- ✅ Raw transaction signatures
- ✅ Parsed trade data with token symbols
- ✅ Basic USD values and timestamps
- ✅ Fast, reliable access to trading history

### What This Endpoint Does NOT Provide
- ❌ Position calculations or portfolio tracking
- ❌ Real-time price data or current valuations  
- ❌ Advanced analytics or pattern recognition
- ❌ Cached or preprocessed data

This endpoint is intentionally simple and focused on providing clean, raw data for AI analysis without the complexity of position tracking or pricing pipelines. 