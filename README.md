# Wallet Doctor - Solana Trading Coach

A lightweight CLI tool for analyzing Solana wallet trading performance with AI-powered insights. Get machine-readable metrics and actionable coaching advice in minutes.

## Features

- 📊 **Trading Metrics**: Win rate, PnL analysis, hold patterns
- 🤖 **AI Coaching**: OpenAI-powered insights tailored to your trading style
- 💾 **Local Storage**: DuckDB for fast SQL queries, no external database needed
- 🔍 **Deep Analysis**: Identify leak trades, analyze hold durations, estimate slippage
- 🎯 **Actionable Insights**: Specific suggestions to improve your trading

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set API Keys

```bash
export HELIUS_KEY="your-helius-api-key"
export CIELO_KEY="your-cielo-api-key"
export OPENAI_KEY="your-openai-api-key"
```

### 3. Load Wallet Data

```bash
python coach.py load YOUR_WALLET_ADDRESS
# Or multiple wallets:
python coach.py load WALLET1,WALLET2,WALLET3
```

### 4. Start Coaching Session

```bash
python coach.py chat
```

## Commands

### `load` - Fetch and Cache Wallet Data
```bash
python coach.py load ADDRESS [--limit 500]
```
Fetches transaction history from Helius and PnL data from Cielo.

### `stats` - View Wallet Statistics
```bash
python coach.py stats
```
Displays comprehensive metrics including:
- Win rate analysis
- Hold pattern distribution
- Portfolio summary
- Quick insights

### `chat` - Interactive Coaching
```bash
python coach.py chat
```
Opens an AI-powered chat session. Quick prompts available:
- `general` - Overall performance analysis
- `risk` - Risk management evaluation
- `timing` - Entry/exit timing patterns
- `losses` - Review biggest losses
- `psychology` - Trading psychology patterns

### `analyze` - One-Shot Analysis
```bash
python coach.py analyze ADDRESS "What are my biggest trading mistakes?"
```

### `clear` - Clear Cache
```bash
python coach.py clear
```

## Architecture

```
wallet-doctor/
├── coach.py          # CLI entry point
├── data.py           # API data fetching
├── transforms.py     # Data normalization
├── analytics.py      # Metrics calculation
├── llm.py           # AI coaching logic
└── coach.db         # Local DuckDB storage
```

## Example Usage

### Basic Analysis
```bash
# Load wallet data
python coach.py load 5Xg2n8mHZrKFnwfBDVxZRHqJLEG9L3FJRCDcxRKwiHzE

# View statistics
python coach.py stats

# Start coaching
python coach.py chat
> How can I improve my win rate?
```

### Advanced Queries
```bash
# Direct SQL queries on cached data
duckdb coach.db
> SELECT token_mint, COUNT(*) as trades, AVG(token_amount) as avg_size 
  FROM tx WHERE type LIKE '%swap%' GROUP BY token_mint;
```

## Metrics Explained

- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of average win to average loss
- **Hold Duration**: Time between entry and exit
- **Quick Flips**: Trades held less than 1 hour
- **Leak Trades**: Losses exceeding 100 SOL

## API Requirements

- **Helius**: Enhanced Transactions API for decoded on-chain data
- **Cielo**: PnL endpoints for profit/loss calculations
- **OpenAI**: GPT-4 for coaching insights

## Future Enhancements

- [ ] Real-time slippage calculation with Jupiter prices
- [ ] Discord bot integration
- [ ] Progress tracking over time
- [ ] Custom alert thresholds
- [ ] Multi-wallet portfolio analysis

## License

MIT