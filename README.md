# WalletDoctor API V3

High-performance Solana wallet trading analytics using RPC + batch fetching.

## Overview

WalletDoctor fetches and analyzes trading data directly from the Solana blockchain using Helius RPC endpoint with optimized batching. Achieves <20s response time for wallets with 5,000+ trades.

## Architecture

```
src/
├── api/
│   └── wallet_analytics_api_v3.py    # Flask REST API
└── lib/
    ├── blockchain_fetcher_v3.py      # Core fetcher (RPC + batching)
    └── blockchain_fetcher_v3_fast.py # Optimized parallel version
```

### Key Performance Features

- **RPC Endpoint**: Uses `getSignaturesForAddress` with 1000-signature pages
- **Parallel Batching**: Fetches transactions in 100-tx batches concurrently
- **Smart Caching**: Reuses price data across requests
- **Rate Limiting**: Semaphore-based concurrency control (40 parallel requests)

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
        "signatures_fetched": 9255,
        "trades_parsed": 6424,
        "parse_rate": "69.4%"
    },
    "analytics": {
        "total_trades": 6424,
        "total_volume": 125000.50,
        "unique_tokens": 806,
        "tokens_traded": ["SOL", "PUMP", "BONK", ...]
    },
    "elapsed_seconds": 19.2
}
```

### `POST /v4/analyze` (with skip_pricing)
Fast analysis without price data.

### `POST /v4/prices`
Batch price fetching for trades.

### `GET /v4/progress/{token}`
Check analysis progress (for future streaming).

### `GET /health`
Health check endpoint.

## Quick Start

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export HELIUS_KEY=your-helius-api-key
export BIRDEYE_API_KEY=your-birdeye-api-key

# Run locally
python src/api/wallet_analytics_api_v3.py

# Run performance test
pytest tests/test_perf_ci.py
```

### Production (Railway)
```bash
# Deploy
railway up

# Set environment variables
railway variables set HELIUS_KEY=xxx
railway variables set BIRDEYE_API_KEY=xxx
```

## Performance

- **Target**: <20 seconds for 5,000+ trade wallets
- **Signature Fetching**: ~7s for 9,000 signatures (16 pages @ 1000/page)
- **Transaction Batching**: ~10s for 93 batches (40 concurrent)
- **Total**: ~19s end-to-end

## Technical Details

- **RPC Pagination**: 1000 signatures per page via Helius RPC
- **Batch Fetching**: 100 transactions per batch via Enhanced API
- **Concurrency**: 40 parallel requests (Helius paid plan limit)
- **Price Caching**: In-memory LRU + file-backed persistence
- **Error Handling**: Exponential backoff on 429s

## License

MIT
