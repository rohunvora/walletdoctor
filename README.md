# WalletDoctor 🏥

Analyze your Solana wallet trading patterns and get psychologically accurate insights based on verifiable data.

## Quick Start

```bash
# Set your API keys
export CIELO_KEY="your_cielo_api_key"
export OPENAI_API_KEY="your_openai_key"  # Optional, for better insights

# Run analysis
python walletdoctor_main.py YOUR_WALLET_ADDRESS
```

## What It Does

WalletDoctor analyzes your trading behavior using only verifiable data:
- Win rate and P&L
- Hold time patterns (winners vs losers)
- Position sizing impact
- Trading frequency

## What It Doesn't Do

The system is constrained to avoid false narratives:
- ❌ No speculation about "cutting winners early" (we don't know future prices)
- ❌ No assumptions about market conditions
- ❌ No guessing about your emotional state
- ✅ Only claims backed by actual data

## Example Output

```
You made 847 trades in 30 days. That's 28 trades per day.

Here's what actually happened:
- 73% of those trades lost money
- You held losers 4.2x longer than winners
- Your biggest positions lost 3x more than your smallest ones

The data shows position size matters: your large positions 
average -$1,235 per trade while small positions average -$287.

One change: Cap position size at $5,000 until your win rate improves.
```

## Architecture

```
walletdoctor_main.py          # Main entry point
├── scripts/
│   ├── data.py              # API fetching
│   └── transforms.py        # Data normalization
└── src/walletdoctor/
    ├── features/            # Pattern detection
    └── insights/            # Constrained synthesis
```

## Features

### 🧠 Deep Behavioral Analysis
- **Pattern Detection**: Multi-metric analysis reveals hidden behaviors
- **Statistical Validation**: Prevents false conclusions with p-values and effect sizes
- **Psychological Mapping**: Connects patterns to subconscious drivers
- **Harsh Truths**: Forces self-reflection through uncomfortable reality

### 📊 Comprehensive Metrics
- Win rate and profit factor analysis
- Hold time patterns (winner vs loser asymmetry)
- Position sizing consistency
- Revenge trading detection
- FOMO spiral identification
- Overtrading indicators

### 🎯 Actionable Insights
- Specific rules, not vague advice
- Confidence scores for each insight
- Severity ratings (Critical/High/Moderate)
- Step-by-step fixes for each pattern

## 📋 Prerequisites

- Python 3.8+
- API keys for:
  - [Helius](https://dev.helius.xyz/) - For transaction data
  - [Cielo](https://cielo.finance/) - For PnL analysis
  - [OpenAI](https://platform.openai.com/) - For AI insights

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/walletdoctor.git
cd walletdoctor
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up API keys:
```bash
# Copy the example environment file
cp env.example .env

# Edit .env and add your API keys
# Or export them in your shell:
export HELIUS_KEY="your-helius-api-key"
export CIELO_KEY="your-cielo-api-key"
export OPENAI_API_KEY="your-openai-api-key"
```

## 🎯 Usage

### Load wallet data:
```bash
python coach.py load <wallet-address>
```

### View statistics:
```bash
python coach.py stats
```

### Get AI analysis:
```bash
python coach.py analyze
```

### Interactive chat with AI coach:
```bash
python coach.py chat
```

### Clear cached data:
```bash
python coach.py clear
```

## 📊 Example Output

```
📊 Wallet Statistics

Performance Summary
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Metric           ┃ Value       ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Tokens Traded    │ 800         │
│ Token Win Rate   │ 25.62%      │
│ Winning Tokens   │ 205         │
│ Losing Tokens    │ 595         │
│ Realized PnL     │ $332,499.00 │
│ Unrealized PnL   │ $333,739.28 │
│ Median Hold Time │ 9.9 minutes │
└──────────────────┴─────────────┘
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⚠️ Important Security Note

**Never commit API keys to version control!** Always use environment variables or a `.env` file (which should be in `.gitignore`).

## 📝 License

MIT License - see LICENSE file for details.

## Known Issues

### Cielo API Limitations

Some wallets return empty data from Cielo's API even though they show trading history on Cielo's website. This is a known issue with their API, not with WalletDoctor.

**Example problematic wallet:**
- `DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm` - Shows 3,718 trades on website, but API returns 0

**Workaround:** 
- Use a different wallet
- View the wallet directly on [Cielo's website](https://app.cielo.finance)