# WalletDoctor Analytics

A pure analytics microservice for trading data analysis. Upload CSV → Get comprehensive metrics → Let GPT handle the narrative.

## What This Is

WalletDoctor V2 is a complete refactor from live blockchain monitoring to CSV-based batch analysis. The service performs heavy mathematical computations on trading data and returns structured JSON metrics that can be consumed by LLMs or other applications.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate test data
python generate_test_csv.py

# Test analytics directly
python wallet_analytics_service.py test_trades.csv

# Start API server
python wallet_analytics_api.py

# Test API endpoint
curl -X POST -F "file=@test_trades.csv" http://localhost:5000/analyze
```

## CSV Format

Your CSV must include these columns:
- `timestamp` - ISO format datetime
- `action` - buy/sell/swap_in/swap_out
- `token` - Token symbol
- `amount` - Token quantity
- `price` - Price per token
- `value_usd` - Total USD value
- `pnl_usd` - Profit/loss (0 for buys)
- `fees_usd` - Transaction fees

## What You Get

The service returns comprehensive JSON analytics:

```json
{
  "summary": {
    "total_pnl_usd": -215706.61,
    "win_rate_pct": 20.5,
    "profit_factor": 0.09
  },
  "pnl_analysis": { ... },
  "fee_analysis": { ... },
  "timing_analysis": { ... },
  "risk_analysis": { ... },
  "psychological_analysis": { ... }
}
```

## Architecture

- **Analytics Engine** (`wallet_analytics_service.py`) - Core computation engine
- **Web API** (`wallet_analytics_api.py`) - Flask-based HTTP endpoint
- **No blockchain dependencies** - Pure mathematical analysis
- **Timeout-safe** - Designed for GPT's 30-second limit

## Deployment

### Heroku
```bash
git push heroku main
```

### Railway
Use the included `railway_deploy.json` configuration.

### Environment Variables
- `PORT` - Server port (default: 5000)
- `API_BASE_URL` - Public URL for OpenAPI spec
- `FLASK_ENV` - Set to 'production' for deployment

## GPT Integration

1. Deploy API to public URL
2. Get OpenAPI spec from `/openapi.json`
3. Add as GPT Action in ChatGPT
4. Let GPT handle the coaching narrative

## Files

- `wallet_analytics_service.py` - Core analytics engine
- `wallet_analytics_api.py` - Web API wrapper
- `generate_test_csv.py` - Test data generator
- `requirements.txt` - Python dependencies
- `WALLETDOCTOR_V2_ARCHITECTURE.md` - Detailed architecture
- `example_analytics_output_formatted.json` - Example output

## License

MIT