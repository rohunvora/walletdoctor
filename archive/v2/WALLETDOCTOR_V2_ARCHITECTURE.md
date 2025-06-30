# WalletDoctor V2 Architecture

## Overview

WalletDoctor V2 is a complete refactor from live blockchain monitoring to CSV-based batch analysis. The new architecture separates analytics computation from narrative generation, with GPT handling only the coaching aspect.

## Architecture Components

### 1. Analytics Microservice (`wallet_analytics_service.py`)
- **Purpose**: Pure Python metrics calculation engine
- **Input**: CSV with trading data (timestamp, action, token, amount, price, value_usd, pnl_usd, fees_usd)
- **Output**: Comprehensive JSON analytics report
- **Key Features**:
  - P&L analysis (win rate, profit factor, Sharpe ratio)
  - Fee impact analysis
  - Timing patterns (hold times, best hours, overtrading)
  - Risk metrics (drawdown, position sizing, streaks)
  - Psychological patterns (revenge trading, FOMO, tilt detection)
  - No blockchain dependencies
  - Timeout-safe (<25 seconds)

### 2. Web API Layer (`wallet_analytics_api.py`)
- **Purpose**: HTTP endpoint for GPT Actions integration
- **Framework**: Flask (lightweight, simple)
- **Endpoints**:
  - `/analyze` - POST endpoint accepting CSV file
  - `/health` - Health check
  - `/openapi.json` - OpenAPI spec for GPT Actions
- **Security**:
  - File size limits (10MB)
  - CSV validation
  - Timeout protection (25s)
  - Wallet address hashing

### 3. GPT Integration (via Actions)
- **Purpose**: Natural language narrative generation
- **Integration**: OpenAPI specification
- **Responsibilities**:
  - Interpret JSON metrics
  - Generate coaching narrative
  - Maintain "ruthless coach" personality
  - Never touch raw data or calculations

## Data Flow

```
User uploads CSV → GPT Action → Analytics API → Analytics Service
                                      ↓
                         JSON metrics report
                                      ↓
                    GPT generates narrative ← User sees report
```

## CSV Format Requirements

Required columns:
- `timestamp`: ISO format datetime
- `action`: buy/sell/swap_in/swap_out
- `token`: Token symbol
- `amount`: Token amount
- `price`: Price per token
- `value_usd`: Total USD value
- `pnl_usd`: Profit/loss (0 for buys)
- `fees_usd`: Transaction fees

## Deployment Options

### Local Development
```bash
# Install dependencies
pip install flask pandas numpy

# Run the API
python wallet_analytics_api.py

# Test with sample data
python generate_test_csv.py
curl -X POST -F "file=@test_trades.csv" http://localhost:5000/analyze
```

### Production Deployment
- Deploy to any Python hosting (Heroku, Railway, AWS Lambda)
- Set environment variables:
  - `PORT`: Server port
  - `API_BASE_URL`: Public URL for OpenAPI spec
  - `FLASK_ENV`: production

## GPT Actions Configuration

1. In ChatGPT, create new GPT
2. Add Action with OpenAPI spec from `/openapi.json`
3. Test with sample CSV upload
4. Configure system prompt with coaching personality

## Security Considerations

- No wallet addresses in responses (hashed)
- File size limits prevent DoS
- Timeout protection for GPT's 30s limit
- Input validation on all fields
- "Not financial advice" disclaimers

## Migration from V1

Key differences:
- No live monitoring (batch analysis only)
- No blockchain APIs (Cielo, Birdeye)
- No Telegram integration
- Single-shot analysis (not conversational)
- CSV as single source of truth

## Future Enhancements

- Support for multiple CSV formats
- Historical comparison reports
- Portfolio-level analysis
- API authentication
- Caching for repeated analysis
