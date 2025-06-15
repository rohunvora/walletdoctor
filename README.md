# WalletDoctor 🏥

Analyze your Solana wallet trading patterns and get harsh, direct insights backed by data. No fluff, no generic advice - just brutal truths about your trading behavior.

## 🚀 Quick Start (Web Interface)

Visit the deployed app: **[Your Railway URL Here]**

Or run locally:
```bash
# Set your API keys
export CIELO_KEY="your_cielo_api_key"
export HELIUS_KEY="your_helius_api_key"
export OPENAI_API_KEY="your_openai_key"  # Optional, for AI insights

# Run the web interface
python web_app_v2.py
```

Then visit: http://localhost:5002

## 🎯 What It Does

WalletDoctor provides brutal, actionable insights about your trading:

**Before**: "Consider improving your risk management strategy"  
**After**: "You hold losers 3.2x longer than winners. This cost you $127,453."

### Core Insights
- **Position Size Analysis**: Which entry sizes actually make money
- **Hold Time Patterns**: Your profitable vs unprofitable time windows
- **Bag Holding Detection**: Exactly how much holding losers costs you
- **Overtrading Alerts**: When you're gambling, not trading
- **Win Rate Reality**: No sugar coating, just facts

## 🛠️ Architecture

```
web_app_v2.py                # Flask web interface
├── scripts/
│   ├── coach.py            # Core CLI commands
│   ├── data.py             # Helius/Cielo API integration
│   ├── transforms.py       # Data normalization
│   ├── analytics.py        # Statistical analysis
│   ├── harsh_insights.py   # Brutal truth generation
│   └── instant_stats.py    # Quick baseline stats
└── src/walletdoctor/
    ├── features/           # Pattern detection
    └── insights/           # Deep psychological analysis
```

## 📋 Prerequisites

- Python 3.8+
- API keys for:
  - [Helius](https://dev.helius.xyz/) - Transaction data
  - [Cielo](https://cielo.finance/) - P&L analysis
  - [OpenAI](https://platform.openai.com/) - AI insights (optional)

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/rohunvora/walletdoctor.git
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
export OPENAI_API_KEY="your-openai-api-key"  # Optional
```

## 💻 CLI Usage (Advanced)

### Load wallet data:
```bash
python scripts/coach.py load <wallet-address>
```

### View statistics:
```bash
python scripts/coach.py stats
```

### Get instant analysis:
```bash
python scripts/coach.py instant <wallet-address>
```

### Interactive AI chat:
```bash
python scripts/coach.py chat
```

## 📊 Example Output

```
💰 YOUR POSITION SIZE SWEET SPOT
Best size range: $1K-5K (Total P&L: $127,453)
Worst size range: >$50K (Total P&L: -$84,291)
$1K-5K win rate: 47%
>$50K win rate: 18%
THE FIX: Stick to $1K-5K positions. Your >$50K trades are ego, not edge.

⏰ YOUR PROFITABLE TIME WINDOW
<10min: 18% win rate, -$67k total
2-6hr: 52% win rate, +$89k total ← YOUR ZONE
>24hr: 22% win rate, -$94k total
THE FIX: Set alerts at 2hr and 6hr. That's your zone.
```

## 🚀 Deployment

The app is designed to run on [Railway](https://railway.app):

1. Fork this repository
2. Connect Railway to your GitHub
3. Set environment variables in Railway:
   - `HELIUS_KEY`
   - `CIELO_KEY`
   - `OPENAI_API_KEY` (optional)
4. Deploy!

See [docs/DEPLOY_TO_RAILWAY.md](docs/DEPLOY_TO_RAILWAY.md) for detailed instructions.

## 🧠 Deep Behavioral Analysis

The system detects patterns like:
- **Loss Aversion**: Holding losers longer than winners
- **Revenge Trading**: Increasing size after losses
- **FOMO Spirals**: Quick trades with poor outcomes
- **Overtrading**: Too many positions, too little thought
- **Position Sizing Issues**: When bigger isn't better

Each pattern is:
- Validated with statistical significance (p-values)
- Backed by multiple data points
- Given a confidence score
- Paired with a specific, actionable fix

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⚠️ Security Note

**Never commit API keys to version control!** Always use environment variables or a `.env` file (which should be in `.gitignore`).

## 📝 License

MIT License - see LICENSE file for details.