# Pocket Trading Coach 🤖

A real-time Telegram bot that monitors your Solana trades and helps you recognize patterns through conversational coaching. No generic advice - just personalized questions based on YOUR trading history.

## What It Does

The bot watches your trades as they happen and asks thoughtful questions to build self-awareness:

**You**: *buys BONK for the 7th time*  
**Bot**: "BONK again? Last 6 times cost you -$4,732. What's different now?"

**You**: *enters 3x normal position size*  
**Bot**: "Big jump in size (3.2×). Conviction play or revenge trade?"

**You**: *sells at -49% loss*  
**Bot**: "Cutting MAG losses? What changed your thesis?"

## Key Features

### 🧠 State-Based Memory
- Never asks the same question twice until you answer
- Remembers conversations across bot restarts
- Tracks conversation state per token
- Complete user isolation for privacy

### 📊 Real-Time Monitoring
- Detects trades within 5 seconds
- Works with Pump.fun, Raydium, and all major Solana DEXes
- Shows P&L data (realized + unrealized)
- Automatic wallet monitoring on bot startup

### 💬 Smart Conversations
- P&L-aware responses (different for profits vs losses)
- Risk context when you're overexposed
- Pattern recognition from your trading history
- Natural callbacks to previous conversations

### 🎯 Pattern Detection
- **Repeat tokens**: Warns when trading same tokens repeatedly
- **Position sizing**: Alerts on unusually large trades
- **Hold time**: Identifies when you're outside profit windows
- **Immediate patterns**: Dust trades, round numbers, late night trading

## Quick Start

### Prerequisites
- Python 3.8-3.12
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- API Keys:
  - [Helius](https://dev.helius.xyz/) - Transaction data
  - [Cielo](https://cielo.finance/) - P&L tracking
  - [OpenAI](https://platform.openai.com/) (optional) - Enhanced tagging

### Installation

```bash
# Clone repository
git clone https://github.com/rohunvora/walletdoctor.git
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

### Running the Bot

```bash
# Start the bot
python telegram_bot_coach.py

# Or use management scripts
./management/start_bot.sh   # Start in background
./management/status_bot.sh  # Check status
./management/stop_bot.sh    # Stop bot
```

## Bot Commands

- `/start` - Welcome message and setup
- `/connect <wallet>` - Link your wallet for monitoring
- `/disconnect` - Stop monitoring
- `/stats` - View your trading statistics
- `/note <text>` - Add context to recent trades

## How It Works

1. **Connect Wallet**: Link your Solana wallet with `/connect`
2. **Trade Normally**: Bot monitors all swaps automatically
3. **Answer Questions**: Bot asks contextual questions after trades
4. **Build Awareness**: Your answers help identify patterns
5. **Improve Trading**: Recognize habits through your own words

### Example Conversation

```
🟢 BUY VIBE on Pump.fun
[Trade details...]

Bot: "VIBE again? What's different this time?"
You: "Following the whale who bought"

[Next VIBE trade]
Bot: "Last time you were following a whale. Same thesis?"
You: "No, this time it's the chart setup"

[Bot learns your different strategies]
```

## Architecture

```
Your Wallet → Monitor → Pattern Detection → State Manager → Nudge Engine → Telegram
                ↓                              ↓
          Trade History                 Conversation Memory
```

### Core Components
- `telegram_bot_coach.py` - Main bot application
- `state_manager.py` - Conversation state and memory
- `pattern_service.py` - Trading pattern detection
- `nudge_engine.py` - Question generation engine
- `conversation_manager.py` - Response tracking

## Configuration

Create a `.env` file with:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
HELIUS_KEY=your_helius_key_here
CIELO_KEY=your_cielo_key_here
OPENAI_API_KEY=your_openai_key_here  # Optional
```

## Contributing

We welcome contributions! Key areas for improvement:
- Pattern detection algorithms
- Conversation templates
- P&L calculation accuracy
- Context-aware AI responses

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Documentation

- [Bot Management](BOT_MANAGEMENT.md) - Starting, stopping, monitoring
- [Architecture](docs/ARCHITECTURE.md) - Technical design details
- [AI Implementation Plan](docs/CONTEXT_AWARE_AI_PLAN.md) - Future AI enhancements
- [Testing Guide](TESTING_GUIDE.md) - How to test changes

## Project History

### Previous Iterations
- **Tradebro Analyzer** (`telegram_bot_simple.py`) - One-time wallet analysis bot providing harsh truths
- **Web Interface** (archived) - Flask-based wallet analysis tool

The project evolved from simple wallet analysis to real-time conversational coaching based on user feedback and the realization that behavior change happens in the moment, not from historical reports.

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

*Built with ❤️ for Solana degens who want to trade better*