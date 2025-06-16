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
├── state_manager.py          # Coach bot state management
├── pattern_service.py        # Trading pattern detection
├── nudge_engine.py          # Question generation for coach
├── conversation_manager.py   # User interaction handling
├── metrics_collector.py      # Performance metrics
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
- **State Management**: `state_manager.py` - Maintains conversation state per token
- **Pattern Detection**: `pattern_service.py` - Identifies trading patterns
- **Response Generation**: `nudge_engine.py` - Creates contextual questions
- **Database**: `pocket_coach.db` - Stores user data and conversations

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

### Coach Bot Flow
```
User Trade → Blockchain → Monitor → Pattern Detection → State Check → Response
                                           ↓                ↓
                                    Database Storage   Conversation Memory
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
- `OPENAI_API_KEY` - OpenAI for AI features (optional)

### Database Schema
The coach bot uses DuckDB with tables for:
- User wallets and monitoring status
- Transaction history
- Conversation state
- Trading patterns
- User annotations

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

# Run specific test
python -m pytest tests/unit/test_state_manager.py
```

### Adding Features
1. For coach bot features, modify the appropriate component
2. For shared functionality, add to `scripts/`
3. Update tests and documentation
4. Test with both bots if applicable

## Archived Components

The `archive/` directory contains deprecated components that are no longer actively maintained:
- **Web Interface**: Flask-based web app for wallet analysis (use Telegram bots instead)
- **Railway Deployment**: Deployment configuration for the web app
