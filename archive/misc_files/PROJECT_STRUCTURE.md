# Project Structure

## Overview
This repository contains two Telegram bots for Solana trading analysis:

1. **Pocket Trading Coach** (`telegram_bot_coach.py`) - Real-time trade monitoring and coaching
2. **Tradebro Analyzer** (`telegram_bot_simple.py`) - Harsh wallet analysis

## Directory Structure

```
walletdoctor/
├── telegram_bot_coach.py      # Real-time trading coach bot
├── telegram_bot_simple.py     # Wallet analyzer bot
├── price_history_service.py   # Price monitoring and storage
├── diary_api.py              # Data access layer with caching
├── prompt_builder.py         # Context builder for GPT
├── gpt_client.py            # OpenAI GPT integration
├── coach_prompt_v1.md       # Coach L personality prompt
├── pocket_coach.db          # Production database
├── bot.log                  # Current log file
│
├── scripts/                 # Shared utilities
│   ├── pnl_service.py      # P&L data integration
│   ├── price_service.py    # Price data and caching
│   ├── token_metadata.py   # Token information
│   ├── personal_history.py # User trading history
│   ├── notification_engine.py
│   ├── monitoring_manager.py
│   ├── transaction_parser.py
│   ├── link_generator.py
│   ├── data.py            # Data loading utilities
│   ├── analytics.py       # Analysis functions
│   ├── instant_stats.py   # Quick statistics
│   ├── grading_engine.py  # Trading grades
│   ├── creative_trade_labels.py
│   ├── wisdom_generator.py
│   ├── coach.py           # CLI coach interface
│   ├── llm.py            # LLM integration
│   └── transforms.py      # Data transformations
│
├── management/            # Bot management scripts
│   ├── start_bot.sh      # Start the coach bot
│   ├── stop_bot.sh       # Stop the coach bot
│   ├── status_bot.sh     # Check bot status
│   └── restart_bot.sh    # Restart the bot
│
├── docs/                  # Documentation
│   ├── ARCHITECTURE.md    # System architecture
│   ├── PRICE_HISTORY_IMPLEMENTATION.md # Price tracking docs
│   ├── CONTEXT_AWARE_AI_PLAN.md  # AI implementation plan
│   ├── REPOSITORY_CLEANUP_PLAN.md # Cleanup strategy
│   ├── telegram_setup.md  # Bot setup guide
│   └── archive/          # Historical documentation
│
├── tests/                # Test suite
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
│
├── archive/             # Archived/deprecated components
│   ├── web/            # ARCHIVED: Web interface (no longer maintained)
│   ├── db_migrations.py # ARCHIVED: Web app dependency
│   ├── old_stack_v1/   # ARCHIVED: Complex abstraction layers
│   │   ├── state_manager.py
│   │   ├── pattern_service.py
│   │   ├── nudge_engine.py
│   │   ├── conversation_manager.py
│   │   └── enhanced_context_builder.py
│   ├── Procfile        # ARCHIVED: Railway deployment
│   ├── railway.json    # ARCHIVED: Railway config
│   └── RAILWAY_DEPLOYMENT.md # ARCHIVED: Deployment docs
│
├── .cursor/             # Cursor workspace
│   └── scratchpad.md   # Internal documentation
│
├── requirements.txt     # Python dependencies
├── env.example         # Environment variables template
├── .gitignore         # Git ignore rules
├── LICENSE            # MIT license
├── README.md          # Main documentation
├── BOT_MANAGEMENT.md  # Bot operation guide
└── TESTING_GUIDE.md   # Testing instructions
```

## Key Components

### Pocket Trading Coach
The real-time monitoring bot that watches user trades and provides conversational coaching:
- **Entry Point**: `telegram_bot_coach.py`
- **Price Monitoring**: `price_history_service.py` - Continuous price tracking
- **Data Access**: `diary_api.py` - Cached data access with price context
- **AI Integration**: `gpt_client.py` - GPT with function calling
- **Context Building**: `prompt_builder.py` - Minimal context with price data
- **Database**: `pocket_coach.db` - Stores all data including price history

### Database Tables
- `diary` - Event log (trades, messages, responses)
- `user_wallets` - Connected wallets
- `price_snapshots` - Time-series price data
- `user_positions` - Position tracking with peaks
- `user_trades` - Trade history
- `wallet_transactions` - Raw transaction data

### Tradebro Analyzer
The harsh wallet analysis bot that provides brutal insights:
- **Entry Point**: `telegram_bot_simple.py`
- **Database**: Uses temporary databases for each analysis
- **Analysis**: Leverages scripts in `scripts/` directory

### Shared Utilities
The `scripts/` directory contains utilities used by both bots:
- **Data Loading**: `data.py` - Fetches wallet data from APIs
- **Analysis**: `analytics.py`, `instant_stats.py` - Trading analysis
- **P&L Tracking**: `pnl_service.py` - Profit/loss calculations
- **Metadata**: `token_metadata.py`, `price_service.py` - Token info

## Data Flow

### Coach Bot Flow (Lean Pipeline)
```
Wallet → Listener → Diary → Prompt Builder → GPT (with tools) → Telegram
                      ↓                         ↑
                Price History ←←←←←←←←←←←←←← (Real-time context)
```

### Price Monitoring Flow
```
User Trade → Start Monitoring → Every 1 minute → Fetch Price → Store Snapshot
                                                       ↓
                                              Update User Peaks → Send Alerts
```

### Analyzer Bot Flow
```
User Command → Load Wallet Data → Analyze Patterns → Generate Insight → Send Response
                      ↓
                 Temporary DB
```

## Configuration

### Environment Variables
Required in `.env`:
- `TELEGRAM_BOT_TOKEN` - Bot token from BotFather
- `HELIUS_KEY` - Helius API for transaction data
- `CIELO_KEY` - Cielo API for P&L tracking
- `BIRDEYE_API_KEY` - Birdeye API for price data
- `OPENAI_API_KEY` - OpenAI for AI features

### API Integrations
- **Birdeye**: Primary price data source
- **DexScreener**: Fallback for new tokens
- **Cielo**: P&L and trading statistics
- **Helius**: Transaction monitoring

## Development

### Running Locally
```bash
# Coach bot
python telegram_bot_coach.py

# Analyzer bot
python telegram_bot_simple.py
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Test price monitoring
python test_continuous_monitoring.py
```

### Adding Features
1. For coach bot features, modify the appropriate component
2. For shared functionality, add to `scripts/`
3. Update tests and documentation
4. Test with both bots if applicable

## Performance Metrics
- Cold start: <5ms
- Price fetch: ~200ms (cached: <1ms)
- Database write: <10ms with mutex
- GPT response: ~2s with tools

## Recent Changes (June 2025)
- Implemented continuous price monitoring
- Added peak tracking and alerts
- Enhanced AI with price context
- Replaced complex abstraction layers with lean pipeline
- Achieved 1107x performance improvement
