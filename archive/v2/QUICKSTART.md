# WalletDoctor V2 Quick Start

## What's New
- **CSV-based analysis** instead of live blockchain monitoring
- **Pure metrics microservice** - no narrative generation in Python
- **GPT Actions integration** - clean HTTP endpoint
- **One-shot reports** - no chatty back-and-forth

## Setup (5 minutes)

1. **Install dependencies**:
```bash
pip install pandas numpy flask
```

2. **Test locally**:
```bash
# Generate test data
python3 generate_test_csv.py

# Run analytics directly
python3 wallet_analytics_service.py test_trades.csv

# Start API server
python3 wallet_analytics_api.py
```

3. **Test API**:
```bash
# In another terminal
curl -X POST -F "file=@test_trades.csv" http://localhost:5000/analyze
```

## CSV Format

Your CSV must have these columns:
- `timestamp` - ISO format (2024-01-15 14:30:00)
- `action` - buy/sell/swap_in/swap_out
- `token` - Token symbol (SOL, BONK, etc)
- `amount` - Token quantity
- `price` - Price per token
- `value_usd` - Total USD value
- `pnl_usd` - Profit/loss (0 for buys)
- `fees_usd` - Transaction fees

## What You Get

The service returns JSON with:
- **P&L Analysis**: Win rate, profit factor, largest wins/losses
- **Fee Analysis**: Total fees, impact on profits
- **Timing Analysis**: Hold times, best hours, overtrading score
- **Risk Analysis**: Drawdown, position sizing, losing streaks
- **Psychological Analysis**: Revenge trading, FOMO, tilt periods

## GPT Integration

1. Deploy the API to a public URL (Heroku, Railway, etc)
2. Get OpenAPI spec from `/openapi.json`
3. Add as GPT Action in ChatGPT
4. GPT handles the narrative using the coach prompts

## Key Files

- `wallet_analytics_service.py` - Core analytics engine
- `wallet_analytics_api.py` - Flask API wrapper
- `generate_test_csv.py` - Test data generator
- `requirements_v2.txt` - Minimal dependencies

## Next Steps for Rohun

1. **Review the analytics output** - Run the test to see what metrics we calculate
2. **Deploy the API** - Pick your hosting (I recommend Railway for simplicity)
3. **Wire up GPT Actions** - I'll help with the prompt engineering
4. **Test with real data** - Export from your exchange/ledger tool

The heavy math is done. Now we just need to deploy and connect to GPT.

