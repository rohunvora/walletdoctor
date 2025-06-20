# Pocket Trading Coach

A real-time Solana trading coach that monitors your trades and provides contextual insights through Telegram.

## 🎯 Features

- **Real-time Trade Monitoring**: Detects trades within 5 seconds
- **Bankroll Awareness**: Tracks SOL balance and position sizing (% of bankroll)
- **Market Cap Intelligence**: All trades tracked with entry/exit market caps and multipliers
- **Price History Tracking**: Continuous monitoring with 1-minute snapshots
- **Peak Alerts**: Automatic notifications at 3x, 5x, 10x gains
- **Self-Directed Intelligence**: GPT-4 powered responses with data access tools
- **Conversation Memory**: Learns from your trading patterns and conversations
- **Risk Analysis**: Flags oversized positions, FOMO entries, and risky patterns

## 🏗️ Architecture

### Lean Pipeline Design
```
Wallet → Listener → Diary → Prompt Builder → GPT (with tools) → Telegram
                       ↓                         ↑
                Price History ←←←←←←←←←←←←←←← (Real-time context)
```

- **Single Data Flow**: No complex abstraction layers
- **Diary Table**: Append-only source of truth for all events
- **Price Monitoring**: Automatic 1-minute snapshots for all traded tokens
- **GPT Tools**: Self-directed data access for intelligent responses
- **Sub-5ms Performance**: Fast cold start to first response

## 🚀 Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/walletdoctor.git
cd walletdoctor
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
cp env.example .env
# Edit .env and add:
# - TELEGRAM_BOT_TOKEN (from @BotFather)
# - OPENAI_API_KEY (for GPT-4)
# - HELIUS_KEY (for RPC calls)
```

4. **Initialize database**
```bash
python3 -c "import duckdb; db = duckdb.connect('pocket_coach.db'); db.execute(open('diary_schema.sql').read())"
```

5. **Start the bot**
```bash
python3 telegram_bot_coach.py
```

## 💬 Using the Bot

1. **Connect your wallet**
   ```
   /connect YOUR_WALLET_ADDRESS
   ```

2. **Make trades** - The bot will automatically detect and analyze them

3. **Ask questions**
   - "How were my last 5 trades?"
   - "Show me my BONK trades"
   - "What did I trade late at night?"

4. **View stats**
   ```
   /stats
   ```

## 🛠️ Technical Details

### Core Components

- **telegram_bot_coach.py**: Main bot with bankroll tracking
- **diary_api.py**: Data access functions with caching
- **prompt_builder.py**: Minimal context builder
- **gpt_client.py**: OpenAI integration with function calling
- **coach_prompt_v1.md**: Coach L personality prompt

### Data Storage

All data is stored in a single `diary` table:
- Trades with bankroll snapshots
- User messages
- Bot responses
- Exact percentages preserved (no rounding)

### GPT Tools Available

1. `fetch_last_n_trades` - Get recent trades
2. `fetch_trades_by_token` - Get trades for specific token
3. `fetch_trades_by_time` - Get trades in hour range (e.g., late night)
4. `fetch_token_balance` - Calculate current token balance
5. `fetch_wallet_stats` - Get overall win rate and P&L statistics
6. `fetch_token_pnl` - Get detailed P&L for a specific token
7. `fetch_market_cap_context` - Get market cap analysis and risk assessment
8. `fetch_price_context` - Get real-time price data (1h/24h changes, peaks, token age)

### Performance

- Cold start: < 5ms
- Cache: 1000x+ faster for repeated queries
- Rate limit: 3 function calls per message

## 📊 Example Interactions

**After a risky trade:**
```
Bot: 15.2% of your bankroll on BONK? That's 3x your usual size. Conviction play or just tilted?
```

**FOMO detection:**
```
Bot: Buying after a 50% pump in the last hour? That's FOMO territory.
```

**Peak alerts:**
```
Bot: 🚀 PEPE hit 5x from your entry! Consider taking some profits to lock in gains.
```

**Market cap awareness:**
```
Bot: Getting in at $5M? The easy money was at $500K. What's your exit - $20M for a 4x?
```

**Asking about history:**
```
You: How were my last 5 trades?
Bot: [Fetches data] 0 for 5, down $847. Your late night sessions aren't working - 4 of these were between 2-4am.
```

**Pattern recognition:**
```
Bot: Third time buying PEPE after a dump. The last two cost you $312. Different this time?
```

**Price context:**
```
Bot: This token is only 2 hours old and already down 40% from peak. Might be a rug.
```

## 🔧 Development

### Running Tests
```bash
python3 test_lean_pipeline.py
```

### Architecture Decisions
- **No ORM**: Direct SQL for speed and clarity
- **DuckDB**: Fast embedded database
- **Async Everything**: Non-blocking I/O throughout
- **Lean Context**: Only essential data sent to GPT

## 📝 License

MIT License - see LICENSE file

## 🤝 Contributing

Pull requests welcome! Please ensure:
- Tests pass
- No new abstraction layers
- Performance remains < 5s cold start
- Bankroll tracking stays accurate

---

Built with ❤️ for Solana degens who want to trade better.