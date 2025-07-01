# Market Cap API Documentation

## Overview
The Market Cap API provides endpoints for retrieving token market capitalization data with multiple price sources and confidence levels.

## Base URL
```
http://localhost:5001
```

## Authentication
Currently no authentication required (will be added in production).

## Endpoints

### 1. Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "market_cap_api",
  "timestamp": 1234567890
}
```

### 2. Get Market Cap for Single Token
```
GET /v1/market-cap/{token_mint}
```

**Parameters:**
- `token_mint` (path) - Token mint address

**Query Parameters:**
- `slot` (optional) - Specific slot number for historical data
- `timestamp` (optional) - Unix timestamp for cache lookup
- `use_cache` (optional, default: true) - Whether to use cache

**Example:**
```bash
curl "http://localhost:5001/v1/market-cap/So11111111111111111111111111111111111111112?timestamp=1234567890"
```

**Response:**
```json
{
  "token_mint": "So11111111111111111111111111111111111111112",
  "market_cap": 86131118728.8,
  "confidence": "high",
  "source": "helius_raydium",
  "supply": 574207458.192302894,
  "price": 150.0,
  "timestamp": 1234567890,
  "slot": null,
  "cached": false
}
```

**Confidence Levels:**
- `high` - Primary sources (Helius supply + AMM price)
- `est` - Fallback sources (Birdeye, Jupiter, DexScreener)
- `unavailable` - No data available

### 3. Get Market Cap for Multiple Tokens (Batch)
```
POST /v1/market-cap/batch
```

**Request Body:**
```json
{
  "tokens": [
    "So11111111111111111111111111111111111111112",
    {
      "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      "slot": 12345
    },
    {
      "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
      "timestamp": 1234567890
    }
  ],
  "use_cache": true
}
```

**Notes:**
- Maximum 50 tokens per batch
- Tokens can be specified as strings (mint only) or objects (with slot/timestamp)

**Response:**
```json
{
  "results": [
    {
      "token_mint": "So11111111111111111111111111111111111111112",
      "market_cap": 86131118728.8,
      "confidence": "high",
      "source": "helius_raydium",
      "supply": 574207458.192302894,
      "price": 150.0,
      "timestamp": 1234567890,
      "slot": null,
      "cached": false
    }
  ],
  "count": 3
}
```

### 4. Get Popular Tokens
```
GET /v1/market-cap/popular
```

**Query Parameters:**
- `limit` (optional, default: 20) - Maximum number of tokens

**Response:**
```json
{
  "tokens": [
    {
      "token_mint": "So11111111111111111111111111111111111111112",
      "market_cap": 86131118728.8,
      "confidence": "high",
      "source": "helius_raydium",
      "price": 150.0,
      "timestamp": 1234567890
    }
  ],
  "count": 11
}
```

**Popular Tokens Include:**
- SOL, USDC, USDT, WETH, mSOL, stSOL, BONK, JUP, WIF, RENDER, PYTH

### 5. Get Trending Tokens
```
GET /v1/market-cap/trending
```

**Query Parameters:**
- `limit` (optional, default: 20) - Maximum number of tokens

**Response:**
```json
{
  "tokens": [
    {
      "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
      "market_cap": 1234567890.0,
      "confidence": "est",
      "source": "birdeye_mc",
      "price": 0.001234,
      "timestamp": 1234567890,
      "request_count": 523,
      "cache_hits": 412
    }
  ],
  "count": 20
}
```

**Notes:**
- Returns tokens sorted by request frequency
- Includes request statistics

### 6. Get Service Statistics
```
GET /v1/market-cap/stats
```

**Response:**
```json
{
  "cache": {
    "total_keys": 1523,
    "memory_usage": 45678912,
    "hit_rate": 0.85,
    "evictions": 234
  },
  "precache_service": {
    "tracked_tokens": 87,
    "popular_tokens": 11,
    "total_requests": 15234,
    "total_cache_hits": 12987,
    "hit_rate": 85.2,
    "running": true
  }
}
```

## Error Responses

### 400 Bad Request
```json
{
  "error": "Missing 'tokens' in request body"
}
```

### 404 Not Found
```json
{
  "error": "Endpoint not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Error message",
  "token_mint": "affected_token_mint"
}
```

## Data Sources & Fallback Chain

1. **Primary Source (confidence: "high")**
   - Helius supply data + AMM price from on-chain pools
   - Most accurate for liquid tokens

2. **Fallback Sources (confidence: "est")**
   - **Birdeye**: Historical prices and market data
   - **Jupiter**: Aggregated DEX pricing
   - **DexScreener**: Real-time DEX data

## Usage Examples

### Get SOL Market Cap
```bash
curl "http://localhost:5001/v1/market-cap/So11111111111111111111111111111111111111112"
```

### Get Multiple Token Market Caps
```bash
curl -X POST "http://localhost:5001/v1/market-cap/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "tokens": [
      "So11111111111111111111111111111111111111112",
      "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    ]
  }'
```

### Get Top 10 Popular Tokens
```bash
curl "http://localhost:5001/v1/market-cap/popular?limit=10"
```

### Get Service Stats
```bash
curl "http://localhost:5001/v1/market-cap/stats"
```

## Rate Limits
- No hard rate limits currently
- Requests are tracked for analytics
- Frequently requested tokens are pre-cached

## Performance
- Popular tokens refreshed every 60 seconds
- General cache refresh every 5 minutes
- Response times typically <500ms for cached data
- Uncached requests may take 2-5 seconds

## Environment Variables
```bash
MC_API_PORT=5001  # API port (default: 5001)
FLASK_ENV=development  # or production
``` 