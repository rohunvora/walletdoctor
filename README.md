# WalletDoctor 🏥

Two powerful Telegram bots for Solana traders:

## 🤖 Pocket Trading Coach
Real-time trade monitoring that helps you recognize patterns through conversational coaching. Watches your trades as they happen and asks thoughtful questions.

## 📊 Tradebro Analyzer  
Harsh wallet analysis that shows exactly why you're losing money. No sugar-coating - just brutal truths backed by data.

---

## Pocket Trading Coach - Real-Time Monitoring

### What It Does
Watches your trades and asks thoughtful questions to build self-awareness:

**You**: *buys BONK for the 7th time*  
**Bot**: "BONK again? Last 6 times cost you -$4,732. What's different now?"

**You**: *enters 3x normal position size*  
**Bot**: "Big jump in size (3.2×). Conviction play or revenge trade?"

**You**: *sells at -49% loss*  
**Bot**: "Cutting MAG losses? What changed your thesis?"

### Key Features
- **Real-Time Monitoring**: Detects trades within 5 seconds
- **Smart Conversations**: State-based memory, never repeats questions
- **P&L Awareness**: Different responses for profits vs losses
- **Pattern Recognition**: Learns your habits over time

### Running the Coach Bot
```bash
python telegram_bot_coach.py
```

Commands:
- `/start` - Welcome and setup
- `/connect <wallet>` - Link wallet for monitoring
- `/disconnect` - Stop monitoring
- `/stats` - View trading statistics
- `/note <text>` - Add context to trades

---

## Tradebro Analyzer - Brutal Wallet Analysis

### What It Does
Analyzes your wallet and delivers one perfect insight about why you're losing:

**Input**: Your wallet address  
**Output**: The ONE behavior that's costing you the most money

Examples:
- "You lost $4,732 on BONK. Down 67%. Classic pump chase."
- "23 trades on one token. Each one making it worse."
- "Still holding. Still hoping. Hope isn't a strategy."

### Running the Analyzer Bot
```bash
python telegram_bot_simple.py
```

Commands:
- `/analyze <wallet>` - Get brutal truth about your trading
- `/grade <wallet>` - Trading report card with creative labels

## 🚀 Quick Start

### Prerequisites
- Python 3.8-3.12
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))
- API Keys:
  - [Helius](https://dev.helius.xyz/) - Transaction data
  - [Cielo](https://cielo.finance/) - P&L tracking

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/walletdoctor.git
cd walletdoctor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp env.example .env
# Edit .env with your API keys
```

### Choose Your Bot

**For real-time coaching:**
```bash
python telegram_bot_coach.py
# Or use: ./start_bot.sh
```

**For wallet analysis:**
```bash
python telegram_bot_simple.py
```

## 🏗️ Architecture

### Pocket Trading Coach
```
Your Wallet → Monitor → Pattern Detection → State Manager → Nudge Engine → Telegram
                ↓                              ↓
          Trade History                 Conversation Memory
```

Core files: `telegram_bot_coach.py`, `state_manager.py`, `pattern_service.py`, `nudge_engine.py`

### Tradebro Analyzer
```
Wallet Address → Load Historical Data → Analyze Patterns → Generate Insight → Telegram
```

Core file: `telegram_bot_simple.py`

## 🔒 Privacy & Security

- Each user's data is completely isolated
- No sharing between users
- API keys stored securely in environment variables
- Trade data stored locally in DuckDB

## 🤝 Contributing

We welcome contributions! Key areas:
- Improving pattern detection
- Adding new conversation templates
- Enhancing P&L accuracy
- Building the context-aware AI layer

## 📚 Documentation

- [Bot Management Guide](BOT_MANAGEMENT.md) - Start/stop/monitor the bot
- [Testing Guide](TESTING_GUIDE.md) - How to test changes
- [Architecture Details](.cursor/scratchpad.md) - Internal documentation

## ⚠️ Current Limitations

The bot uses rule-based logic which can sometimes:
- Misclassify user intent ("cut position" while in profit)
- Show incorrect P&L data (API limitations)
- Feel repetitive despite state management

We're building a context-aware AI layer to address these issues.

## 📝 License

MIT License - see LICENSE file for details