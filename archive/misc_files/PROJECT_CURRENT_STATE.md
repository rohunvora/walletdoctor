# Pocket Trading Coach - Current Project State
*Last Updated: December 2024*

## 🎯 Executive Summary

The Pocket Trading Coach is a Telegram bot that monitors Solana wallet trades in real-time and provides analytical coaching feedback. It uses a lean pipeline architecture achieving <5ms performance, integrates with Cielo for P&L data, and speaks the language traders understand - market caps and multipliers.

**Bot Handle**: @mytradebro_bot (⚠️ NOT @mywalletdoctor_bot - wrong token in .env)

## 🏗️ Architecture Overview

### Lean Pipeline Design
```
Wallet → Transaction Parser → Diary (DuckDB) → GPT-4 with Tools → Telegram
```

- **Single source of truth**: DuckDB diary table with JSON data field
- **GPT self-directs**: Uses function calling to fetch needed context
- **Performance**: 4.6ms cold start, <1ms with cache
- **No complex abstractions**: Direct flow, minimal layers

## ✅ What's Working Now

### 1. Market Cap-Centric Trading
- Captures market cap for every trade using DexScreener/Birdeye APIs
- Shows entry → exit progression: "Sold at $5.4M (2.7x from $2M avg entry)"
- Handles multiple buys with Cielo's weighted average calculations
- Coach thinks in mcap terms: "Buying at $4M? Easy money was at $400K"

### 2. P&L Integration
- Cielo API integration for comprehensive P&L data
- Tracks win rate, realized/unrealized gains
- Handles pre-bot trading history automatically
- Shows profit/loss on every sell trade

### 3. Real-time Monitoring
- Monitors wallet for swaps every 5 seconds
- Captures exact trade % of bankroll
- Tracks SOL balance changes via RPC
- Processes all major DEXes (Jupiter, Raydium, etc.)

### 4. GPT Intelligence
Available tools:
- `fetch_last_n_trades` - Recent trading history
- `fetch_trades_by_token` - Token-specific trades
- `fetch_trades_by_time` - Time-based analysis
- `fetch_token_balance` - Current holdings
- `fetch_wallet_stats` - Overall statistics
- `fetch_token_pnl` - Token P&L data
- `fetch_market_cap_context` - Market cap analysis

### 5. Coach L Personality
- Blunt, analytical style
- <60 word responses (80 token limit)
- Market cap and data-driven
- No emojis or fluff

## 📊 Data We Capture

### Trade Data (Per Transaction)
```json
{
  "action": "BUY/SELL",
  "token_symbol": "BONK",
  "sol_amount": 0.5,
  "token_amount": 1000000,
  "bankroll_before_sol": 10.5,
  "bankroll_after_sol": 10.0,
  "trade_pct_bankroll": 4.76,
  "market_cap": 1200000,
  "market_cap_formatted": "$1.2M",
  "price_per_token": 0.0000005,
  "dex": "Raydium",
  "timestamp": "2024-12-11T..."
}
```

### SELL Trade Additions
```json
{
  "realized_pnl_usd": 230,
  "avg_buy_price": 0.0000002,
  "avg_sell_price": 0.0000005,
  "roi_percentage": 150,
  "entry_market_cap": 480000,
  "market_cap_multiplier": 2.5,
  "num_swaps": 3  // Indicates multiple buys
}
```

## 🚫 What's NOT Working / Missing

### 1. Critical Issues
- ✅ **Bot Token Fixed**: Now using correct token for @mytradebro_bot
- **No SOL Price**: Trades shown in SOL only, no USD context
- **Limited Error Recovery**: Some edge cases crash monitoring

### 2. Missing Features
- **Pattern Detection**: No revenge trading or FOMO alerts
- **Market Context**: No 24h changes, volume, or trends
- **Performance Tracking**: No week-over-week comparisons
- **Risk Analysis**: No position sizing recommendations

### 3. Technical Debt
- Linter errors (import resolution issues)
- No automated tests
- Monolithic telegram_bot_coach.py file
- Basic caching (no Redis)

## 📁 Key Files

### Core Bot
- `telegram_bot_coach.py` - Main bot implementation
- `diary_api.py` - Data access layer with GPT tools
- `prompt_builder.py` - Minimal context builder
- `gpt_client.py` - GPT-4 client with function calling
- `coach_prompt_v1.md` - System prompt for Coach L

### Supporting Services
- `scripts/pnl_service.py` - Cielo P&L integration
- `scripts/token_metadata.py` - Token data fetching
- `scripts/transaction_parser.py` - Blockchain parsing
- `scripts/notification_engine.py` - Trade notifications

### Configuration
- `.env` - API keys and bot token (⚠️ WRONG BOT)
- `diary_schema.sql` - Database schema
- `requirements.txt` - Python dependencies

## 🎯 Next Steps (Priority Order)

### 1. ✅ Bot Token Fixed
- Updated .env with correct token for @mytradebro_bot
- Token: 7279868913:AAHekXxuqVhLnT94Am-Q4K-4pmDbvn8xK50

### 2. Add SOL Price Context (High Impact, Low Effort)
```python
# Show trades in both SOL and USD
sol_price = await self.pnl_service.get_sol_price()
trade_size_usd = sol_amount * sol_price
# "Bought BONK at $1.2M mcap (0.5 SOL / $47.50)"
```

### 3. Basic Pattern Detection (High Impact, Medium Effort)
- Revenge trading: Trade within 5 min of loss
- FOMO detection: Buying after 50%+ pump
- Late night degen: Trades between 11pm-5am
- Overtrading: >10 trades per hour

### 4. Performance Trending (Medium Impact, Medium Effort)
- Weekly win rate comparison
- P&L progression charts
- Trade size evolution
- Success by market cap tier

## 🚀 How to Run

### Prerequisites
```bash
# Required environment variables
TELEGRAM_BOT_TOKEN=your_token_here  # ⚠️ Need correct token!
HELIUS_KEY=your_helius_key
OPENAI_API_KEY=your_openai_key
CIELO_API_KEY=your_cielo_key
BIRDEYE_API_KEY=your_birdeye_key
```

### Start the Bot
```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python telegram_bot_coach.py

# Or use management scripts
./management/start_bot.sh
```

### Test Market Cap Features
```bash
# Run mock test (no dependencies needed)
python test_market_cap_mock.py

# Check logs for market cap capture
tail -f logs/bot.log | grep "Market cap"
```

## 📈 Success Metrics

- **Performance**: ✅ <5ms response time achieved
- **Data Quality**: ✅ Exact percentages, no rounding
- **Market Cap**: ✅ Every trade tracked with mcap
- **P&L Accuracy**: ✅ Cielo integration working
- **User Experience**: ⚠️ Need USD context and patterns

## 🔗 Related Documentation

- `.cursor/scratchpad.md` - Detailed development notes
- `BOT_MANAGEMENT.md` - Deployment guide
- `TESTING_GUIDE.md` - Testing procedures
- `MARKET_CAP_TESTING.md` - Market cap feature testing

---

**Remember**: The goal is to be the trading coach every degen needs but doesn't want to admit they need. Blunt feedback, exact data, no BS. 