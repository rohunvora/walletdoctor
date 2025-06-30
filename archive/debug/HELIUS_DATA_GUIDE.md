# Getting Clean Trading Data with Helius API

## Why Helius?

After extensive research, Helius Enhanced Transactions API is the best solution for extracting clean Solana trading data because:

1. **Automatic Parsing** - Recognizes Jupiter swaps, SPL token transfers, and NFT activity out of the box
2. **Free Tier** - 1M credits and 10 req/s is more than enough for most wallets
3. **Clean Data** - Returns structured JSON instead of raw blockchain noise
4. **No Manual Filtering** - Unlike raw blockchain exports with thousands of irrelevant transactions

## Quick Start

### 1. Get a Free Helius API Key

Sign up at https://dev.helius.xyz/ to get your free API key.

### 2. Set Environment Variable

```bash
export HELIUS_KEY="your-api-key-here"
```

### 3. Run the Transformation Script

```bash
# Basic usage
python helius_to_walletdoctor.py 3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2

# Specify output file
python helius_to_walletdoctor.py 3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2 my_trades.csv
```

### 4. Use with WalletDoctor

The generated CSV is ready for WalletDoctor analytics:

```bash
# Test locally
python wallet_analytics_service.py my_trades.csv

# Or upload via API
curl -X POST -F "file=@my_trades.csv" https://your-api.com/analyze
```

## What the Script Does

1. **Fetches Only Swaps** - Filters out transfers, staking, and other noise
2. **Parses Jupiter Routes** - Understands complex swap routing
3. **Calculates P&L** - Uses FIFO accounting for accurate profit/loss
4. **Handles Token Pairs** - SOL↔Token and Token↔Token swaps
5. **Estimates Fees** - Converts SOL gas fees to USD

## Output Format

The script generates a CSV with these columns:
- `timestamp` - ISO format datetime
- `action` - buy/sell
- `token` - Token symbol
- `amount` - Quantity traded
- `price` - Price per token in USD
- `value_usd` - Total trade value
- `pnl_usd` - Profit/loss (0 for buys)
- `fees_usd` - Transaction fees in USD

## Limitations

- **Price Estimates** - Uses fixed $150 SOL price (integrate CoinGecko for accuracy)
- **Token Symbols** - Only maps common tokens; others show as "ABC123..."
- **Complex Routes** - Token↔Token swaps are simplified
- **Historical Data** - Helius data availability varies by wallet age

## Advanced Usage

### Adding Token Mappings

Edit `TOKEN_MINTS` in the script:

```python
TOKEN_MINTS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    # Add your tokens here
}
```

### Integrating Real-Time Prices

Replace the fixed SOL price with CoinGecko API:

```python
import requests

def get_sol_price(timestamp):
    # Convert timestamp to date
    date = datetime.fromtimestamp(timestamp).strftime('%d-%m-%Y')
    
    # Fetch historical price
    url = f"https://api.coingecko.com/api/v3/coins/solana/history?date={date}"
    response = requests.get(url)
    data = response.json()
    
    return data['market_data']['current_price']['usd']
```

## Troubleshooting

### "API Key Invalid"
- Check your HELIUS_KEY environment variable
- Ensure no extra spaces or quotes

### "Rate Limit Exceeded"
- The script already includes delays
- If still hitting limits, increase sleep time

### "No Swaps Found"
- Verify the wallet has trading activity
- Check if wallet address is correct
- Try removing the type filter to see all transactions

### "Price Calculations Wrong"
- The script uses rough estimates
- For accurate P&L, integrate historical price data
- Consider using Birdeye or CoinGecko APIs

## Alternative Solutions

| Solution | Pros | Cons |
|----------|------|------|
| **Helius** (recommended) | Free, parsed data, fast | Price estimates needed |
| **Solscan Pro** | Direct CSV export | Paid, limited to 5k rows |
| **Raw RPC** | Full control | Complex parsing required |
| **Birdeye** | Great token data | More expensive |

## Next Steps

1. **Test with Small Wallet** - Verify output format
2. **Add Price Oracle** - Integrate CoinGecko for accurate USD values
3. **Expand Token List** - Map more token addresses to symbols
4. **Handle Edge Cases** - LP operations, staking rewards, etc.

---

For issues or improvements, check the main WalletDoctor documentation. 