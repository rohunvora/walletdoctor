# WalletDoctor API V3

Real-time Solana wallet trading analytics via blockchain data.

## Overview

WalletDoctor fetches and analyzes trading data directly from the Solana blockchain using Helius API. No CSV uploads needed - just provide a wallet address and get comprehensive trading analytics.

## Architecture

```
src/
├── api/
│   └── wallet_analytics_api_v3.py    # Flask REST API
└── lib/
    ├── blockchain_fetcher_v3.py      # Core blockchain fetcher
    └── blockchain_fetcher_v3_fast.py # Optimized version
```

## API Endpoints

### `POST /analyze`
Analyze a wallet's trading history.

**Request:**
```json
{
    "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
}
```

**Response:**
```json
{
    "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
    "fetch_metrics": {
        "transactions_fetched": 498,
        "trades_parsed": 480,
        "parse_rate": "96.4%"
    },
    "analytics": {
        "total_trades": 480,
        "total_volume": 125000.50,
        "unique_tokens": 47,
        "tokens_traded": ["SOL", "PUMP", "BONK", ...]
    }
}
```

### `GET /health`
Health check endpoint.

### `GET /`
API documentation.

## Quick Start

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python src/api/wallet_analytics_api_v3.py
```

### Production (Railway)
```bash
# Deploy
railway up

# Set environment variables
railway variables set HELIUS_API_KEY=xxx
railway variables set BIRDEYE_API_KEY=xxx
```

## Features

- ✅ Direct blockchain data fetching (no CSV needed)
- ✅ Supports all major Solana DEXes (PUMP_AMM, Jupiter, Raydium, etc.)
- ✅ Real-time price data from Birdeye
- ✅ 100% trade parsing with fallback parser
- ✅ Fast performance (3-10 seconds per wallet)

## Technical Details

- **Pagination**: Fetches all historical transactions
- **Parser**: Falls back to tokenTransfers when events.swap missing
- **Rate Limiting**: Automatic handling of Helius/Birdeye limits
- **Caching**: Price data cached to minimize API calls

## License

MIT
