# Tradebro Project Structure

## Overview
Tradebro is a web-based Solana trading analyzer that provides harsh, direct insights about trading behavior. Built with Flask and deployed on Railway.

## Directory Structure

```
tradebro/
├── web_app_v2.py          # Main Flask web application
├── wsgi_v2.py            # WSGI entry point for Gunicorn
├── startup.py            # Startup script for Railway deployment
├── railway.json          # Railway deployment configuration
├── requirements.txt      # Python dependencies
├── runtime.txt          # Python version specification
├── Procfile             # Process file for deployment
├── setup.py             # Package setup configuration
├── auto_setup.py        # Automated setup script
├── setup_bot.sh         # Bot setup shell script
├── .env.example         # Environment variables template
├── .gitignore          # Git ignore rules
│
├── scripts/            # Core functionality
│   ├── __init__.py
│   ├── coach.py       # Main CLI commands
│   ├── data.py        # Helius/Cielo API integration
│   ├── transforms.py  # Data normalization
│   ├── analytics.py   # Statistical analysis
│   ├── llm.py        # OpenAI integration
│   ├── instant_stats.py     # Quick baseline stats
│   ├── blind_spots.py       # Behavioral pattern detection
│   ├── db_migrations.py     # Database schema management
│   ├── trade_comparison.py  # Trade comparison logic
│   ├── check_db_status.py  # Database debugging utility
│   ├── multi_wallet_simple.py  # Multi-wallet analysis
│   ├── multi_wallet_loader.py  # Multi-wallet data loading
│   └── wisdom_generator.py  # Trading wisdom generation
│
├── src/tradebro/   # Deep analysis engine
│   ├── __init__.py
│   ├── example_integration.py  # Integration examples
│   ├── features/      # Pattern detection
│   │   ├── __init__.py
│   │   ├── behaviour.py
│   │   ├── patterns.py
│   │   ├── pattern_validator.py
│   │   └── realistic_patterns.py
│   ├── insights/      # Insight generation
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   ├── rules.yaml
│   │   ├── deep_generator.py
│   │   ├── deep_rules.yaml
│   │   └── constrained_synthesizer.py
│   ├── llm/          # LLM integration
│   │   ├── __init__.py
│   │   └── prompt.py
│   ├── web/          # Web components
│   └── cli/          # CLI components
│
├── templates_v2/      # Web interface templates
│   └── index_v2.html
│
├── tests/            # Test suite
│   ├── unit/
│   └── integration/
│
├── examples/         # Example scripts
│   ├── example.py
│   ├── deep_analysis_example.py
│   ├── deep_behavioral_analysis.py
│   ├── final_deep_insights_demo.py
│   ├── show_deep_vs_shallow.py
│   └── example_full_narrative.py
│
├── data/            # Data directory (gitignored)
│   └── .gitkeep
│
├── docs/           # Documentation
│   ├── ARCHITECTURE.md      # System architecture
│   ├── TELEGRAM_BOT_FIX_SUMMARY.md
│   ├── TELEGRAM_BOT_UX_IMPROVEMENTS.md
│   ├── bot_improvements.md
│   └── telegram_setup.md
│
├── telegram_bot.py         # Telegram bot implementation
├── run_telegram_bot.py     # Bot runner with API keys
└── telegram_monitor.py     # Real-time monitoring service
```

## Key Components

### Web Interface (`web_app_v2.py`)
- Flask application serving the web UI
- Handles wallet analysis requests
- Manages subprocess calls to coach.py
- Session management for user state

### CLI Engine (`scripts/coach.py`)
- Core analysis commands
- Database operations
- Pattern detection orchestration
- Integration point for all analysis features

### Telegram Bot (`telegram_bot.py`)
- Interactive trading journal
- Pattern annotation and tracking
- Real-time alerts and monitoring

### API Integration (`scripts/data.py`)
- Helius API for transaction data
- Cielo API for P&L data
- Data caching in DuckDB

### Analysis Engine
- `instant_stats.py`: Quick baseline statistics
- `blind_spots.py`: Behavioral pattern detection
- `analytics.py`: Statistical calculations
- `wisdom_generator.py`: Personalized trading insights

### Deep Analysis (`src/tradebro/`)
- Advanced pattern detection with statistical validation
- Psychological mapping of trading behaviors
- Confidence scoring system
- Rule-based insight generation

## Database Schema

### DuckDB Tables
- `tx`: Transaction data from Helius
- `pnl`: Profit/loss data from Cielo
- `trade_annotations`: User notes on trades (Telegram bot)
- `telegram_annotations`: Pattern tracking
- `trade_snapshots`: Historical snapshots

## Environment Variables

Required for deployment:
- `HELIUS_KEY`: Helius API key for transaction data
- `CIELO_KEY`: Cielo API key for P&L data
- `OPENAI_API_KEY`: OpenAI key for AI insights (optional)
- `TELEGRAM_BOT_TOKEN`: Telegram bot token (for bot features)

## Deployment

Deployed on Railway with automatic builds from GitHub pushes. See `RAILWAY_DEPLOYMENT.md` for details. 