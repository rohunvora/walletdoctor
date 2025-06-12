# 🩺 WalletDoctor

> Deep psychological analysis for Solana traders. Not just metrics—insights that change behavior.

## What Makes WalletDoctor Different

Most trading analytics tell you WHAT happened. WalletDoctor tells you WHY—and how to fix it.

### Example Output

```
🎯 You hold losers 27% longer than winners
   Confidence: 87% | Severity: HIGH

📊 ROOT CAUSE: Ego protection and fear of being wrong
💭 YOUR INNER VOICE: "If I don't sell, it's not a real loss"
⚡ HARSH TRUTH: You're not 'being patient'—you're in denial.
✅ THE FIX: Hard stop at -5%. No exceptions.
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