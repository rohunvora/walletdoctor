# Railway Deployment - Environment Variables Summary

## What is Helius?

**Helius** is a Solana infrastructure provider that offers:
- **RPC endpoints** for blockchain queries
- **Transaction APIs** for fetching wallet history
- **Enhanced APIs** for parsed transaction data

WalletDoctor uses Helius to fetch all blockchain data.

## Getting Your Helius Key

1. **Sign up** at https://helius.xyz
2. **Create a project** in your dashboard
3. **Copy your API key** (looks like: `abc123def456...`)
4. Use it as `HELIUS_KEY` environment variable

## Required Environment Variables

```bash
# Helius API Key (REQUIRED)
HELIUS_KEY=your_helius_api_key_here

# Feature Flags (REQUIRED)
UNREALIZED_PNL_ENABLED=true
GPT_EXPORT_ENABLED=true
FEATURE_FLAGS_POSITION_LIMITS=true
FEATURE_FLAGS_PRICE_CONFIDENCE_MIN=0.0
```

## Optional Environment Variables

```bash
# Birdeye API Key (OPTIONAL - for price data)
# Without this, the app works but won't fetch USD prices
BIRDEYE_API_KEY=your_birdeye_key_if_you_have_one

# Performance Settings (OPTIONAL)
POSITION_CACHE_TTL=300
POSITION_UPDATE_TTL=600
MEMORY_GUARDRAIL_MB=512
MAX_WALLET_POSITIONS=100
WEB_CONCURRENCY=2
```

## Notes

- **Helius Free Tier**: 100k credits/month (sufficient for testing)
- **Helius Paid Plans**: Start at $99/month for higher limits
- **Birdeye**: Optional but recommended for accurate USD pricing
- The app constructs the RPC URL automatically: `https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}`

## Quick Test

After deployment, test with:
```bash
curl https://your-railway-url.up.railway.app/health
```

Should return:
```json
{
  "status": "healthy",
  "service": "WalletDoctor GPT Export API",
  "version": "1.1",
  "features": {
    "positions_enabled": true,
    "unrealized_pnl_enabled": true,
    "cost_basis_method": "fifo"
  }
}
``` 