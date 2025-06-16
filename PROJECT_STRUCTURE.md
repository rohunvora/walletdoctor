# Project Structure

```
walletdoctor/
│
├── README.md                    # Main documentation
├── QUICKSTART.md               # Quick setup guide
├── TESTING_GUIDE.md            # Testing documentation
├── RAILWAY_DEPLOYMENT.md       # Deployment guide
├── PROJECT_STRUCTURE.md        # This file
├── LICENSE                     # MIT License
│
├── requirements.txt            # Python dependencies
├── env.example                 # Example environment variables
├── .gitignore                  # Git ignore rules
├── Procfile                    # Railway deployment config
├── runtime.txt                 # Python version for Railway
├── railway.json                # Railway configuration
│
├── scripts/                    # Core business logic
│   ├── __init__.py
│   ├── data.py                 # Data fetching with smart pagination
│   ├── transforms.py           # Data transformation utilities
│   ├── analytics.py            # Trading analysis functions
│   ├── instant_stats.py        # Quick stats generation
│   ├── coach.py                # CLI interface
│   ├── llm.py                  # OpenAI integration
│   ├── wisdom_generator.py     # Trading wisdom generation
│   ├── trade_comparison.py     # Trade pattern comparison
│   └── multi_wallet_simple.py  # Multi-wallet analysis
│
├── src/tradebro/               # Advanced pattern detection
│   ├── features/               # Feature extraction modules
│   ├── insights/               # Insight generation
│   └── llm/                    # LLM integration
│
├── templates_v2/               # Web app templates
│   └── index.html              # Main web interface
│
├── examples/                   # Example wallets
│   └── wallets.txt             # List of example addresses
│
├── data/                       # Data storage
│   └── .gitkeep                # Placeholder
│
├── tests/                      # Test files
│   └── .gitkeep                # Placeholder
│
├── docs/                       # Additional documentation
│   └── ARCHITECTURE.md         # System architecture
│
├── venv/                       # Virtual environment (gitignored)
│
├── coach.db                    # SQLite database (gitignored)
│
├── web_app_v2.py              # Flask web application
├── wsgi_v2.py                 # WSGI configuration
├── telegram_bot_simple.py     # Telegram bot implementation
├── test_telegram_bot.py       # Telegram bot test script
└── test_pagination_comprehensive.py  # Pagination test script
```

## Key Components

### Web Application (`web_app_v2.py`)
- Flask-based web interface
- Real-time wallet analysis
- Interactive visualizations
- Smart pagination for large wallets

### Telegram Bot (`telegram_bot_simple.py`)
- Interactive trading journal
- Simplified one-insight-at-a-time approach
- Pattern tracking and monitoring

### Data Layer (`scripts/data.py`)
- Helius transaction fetching
- Cielo P&L data with smart pagination
- Automatic timeframe fallback (max → 30d → 7d → 1d)
- Early stopping when losers found

### Analytics (`scripts/analytics.py`)
- Position size analysis
- Hold time patterns
- Win rate calculations
- Behavioral pattern detection

### Instant Stats (`scripts/instant_stats.py`)
- Quick wallet analysis
- Key metrics generation
- Pattern identification

## Smart Pagination System

The system now includes intelligent pagination to surface losing trades:

1. **Multi-Page Fetching**: Automatically fetches multiple pages of results
2. **Timeframe Fallback**: If no losers found in all-time data, falls back to shorter periods
3. **Early Stopping**: Stops loading once 5 losers are found
4. **Transparent Loading**: UI shows what timeframe is being displayed

## Database Schema

Uses DuckDB for analytics with tables:
- `transactions`: Raw transaction data
- `pnl`: Position P&L data
- `aggregated_stats`: Overall wallet statistics
- `trading_stats`: Historical performance
- `data_window_info`: Pagination metadata

## Environment Variables

Required:
- `CIELO_KEY`: Cielo API key for P&L data
- `HELIUS_KEY`: Helius API key for transactions
- `OPENAI_API_KEY`: OpenAI key for AI insights (optional)
- `TELEGRAM_BOT_TOKEN`: Telegram bot token (for bot only)

## Testing

Run comprehensive tests:
```bash
python test_pagination_comprehensive.py
```

Test the Telegram bot:
```bash
python test_telegram_bot.py
```

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for detailed testing instructions.

## Core Components

### 1. `telegram_bot_coach.py`
The main bot application that handles:
- User commands (`/connect`, `/stats`, `/note`)
- Real-time wallet monitoring
- Trade detection and processing
- Message handling and responses

### 2. `state_manager.py`
Manages conversation state and memory:
- Token notebooks tracking per-token conversation state
- Open questions queue to prevent duplicates
- Risk context calculation (exposure %, P&L)
- Persistent storage with critical event saves
- User isolation and thread safety

### 3. `nudge_engine.py` 