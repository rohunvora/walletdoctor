# Tradebro 🏥

Analyze your Solana wallet trading patterns and get harsh, direct insights backed by data. No fluff, no generic advice - just brutal truths about your trading behavior.

## 🚀 Quick Start

### Web Interface
```bash
# Set your API keys
export CIELO_KEY="your_cielo_api_key"
export HELIUS_KEY="your_helius_api_key"
export OPENAI_API_KEY="your_openai_key"  # Optional, for AI insights

# Run the web interface
python web_app_v2.py
```

Visit: http://localhost:5002

### Telegram Bot
```bash
# Set up your bot token
export TELEGRAM_BOT_TOKEN="your_bot_token"

# Run the bot
python telegram_bot_simple.py
```

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

## 🎯 What It Does

Tradebro provides brutal, actionable insights about your trading:

**Before**: "Consider improving your risk management strategy"  
**After**: "You hold losers 3.2x longer than winners. This cost you $127,453."

### Core Insights
- **Position Size Analysis**: Which entry sizes actually make money
- **Hold Time Patterns**: Your profitable vs unprofitable time windows
- **Bag Holding Detection**: Exactly how much holding losers costs you
- **Overtrading Alerts**: When you're gambling, not trading
- **Win Rate Reality**: No sugar coating, just facts

## 🛠️ Features

### Web Application
- Instant wallet analysis with visual insights
- Interactive charts and statistics
- Smart pagination to surface losing trades (even for wallets with 100+ winners)
- Export capabilities for further analysis
- Responsive design for mobile and desktop

### Telegram Bot
- Interactive trading journal
- Pattern annotation and tracking
- Real-time monitoring and alerts
- Personalized trading rules based on your patterns

### Smart Data Loading
- **Pagination Support**: Automatically fetches multiple pages to find losers
- **Adaptive Timeframes**: Falls back to shorter periods (30d, 7d, 1d) when needed
- **Early Stopping**: Stops loading once sufficient losers are found
- **Transparent Loading**: Shows exactly what data period is being displayed

### CLI Tools
- Batch wallet analysis
- Deep behavioral pattern detection
- Multi-wallet comparison
- Database management

## Features

- **Real-time Trade Monitoring**: Detects swaps within 5 seconds
- **Pattern Recognition**: Identifies repeat tokens, position sizing, hold times
- **Conversational Nudges**: Asks thoughtful questions, not generic alerts
- **P&L Integration**: Shows realized and unrealized profit/loss
- **Trade Notes**: Annotate trades to help the bot learn your style
- **Personal Stats**: Track your win rate, average hold times, and patterns

## State-Based Memory System

The bot uses a sophisticated state management system to ensure conversations feel natural and never repetitive:

- **Token Notebooks**: Maintains conversation state for each token you trade
- **No Duplicate Questions**: Won't ask the same question twice until you answer
- **Risk Context**: Automatically adds portfolio exposure or P&L context when relevant
- **Persistent Memory**: Survives bot restarts and remembers all conversations
- **User Isolation**: Each user has completely separate conversation state

Example:
- First BONK trade: "BONK again? What's different this time?"
- Second BONK trade: [No question - waiting for your answer]
- High exposure trade: "You're at 22% of bankroll in VIBE—same whale thesis?"

## 📋 Prerequisites

- Python 3.8-3.12
- API keys:
  - [Helius](https://dev.helius.xyz/) - Transaction data
  - [Cielo](https://cielo.finance/) - P&L analysis
  - [OpenAI](https://platform.openai.com/) - AI insights (optional)
  - [Telegram Bot Token](https://core.telegram.org/bots#how-do-i-create-a-bot) - For bot features

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tradebro.git
cd tradebro
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
3. Set environment variables in Railway
4. Deploy!

See [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for detailed instructions.

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

## 📚 Documentation

- [Project Structure](PROJECT_STRUCTURE.md) - Detailed code organization
- [Architecture](docs/ARCHITECTURE.md) - System design and components
- [Quick Start Guide](QUICKSTART.md) - Get started in 5 minutes
- [Railway Deployment](RAILWAY_DEPLOYMENT.md) - Deploy to production

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⚠️ Security Note

**Never commit API keys to version control!** Always use environment variables or a `.env` file (which should be in `.gitignore`).

## 📝 License

MIT License - see LICENSE file for details.