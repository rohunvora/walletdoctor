# WalletDoctor Project Structure

## Overview
WalletDoctor is a web-based Solana trading analyzer that provides harsh, direct insights about trading behavior. Built with Flask and deployed on Railway.

## Directory Structure

```
walletdoctor/
├── web_app_v2.py          # Main Flask web application
├── wsgi_v2.py            # WSGI entry point for Gunicorn
├── startup.py            # Startup script for Railway deployment
├── railway.json          # Railway deployment configuration
├── requirements.txt      # Python dependencies
├── runtime.txt          # Python version specification
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
│   ├── harsh_insights.py    # Brutal truth generation
│   ├── instant_stats.py     # Quick baseline stats
│   ├── blind_spots.py       # Behavioral pattern detection
│   ├── db_migrations.py     # Database schema management
│   ├── trade_comparison.py  # Trade comparison logic
│   ├── check_db_status.py  # Database debugging utility
│   ├── multi_wallet_simple.py  # Multi-wallet analysis
│   └── multi_wallet_loader.py  # Multi-wallet data loading
│
├── src/walletdoctor/   # Deep analysis engine
│   ├── __init__.py
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
│   └── llm/          # LLM integration
│       ├── __init__.py
│       └── prompt.py
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
└── docs/           # Documentation
    ├── README.md
    ├── DEPLOY_TO_RAILWAY.md
    ├── QUICK_START_MVP.md
    ├── MVP_ROADMAP.md
    ├── WALLETDOCTOR_TECHNICAL_DESIGN.md
    ├── SCRATCHPAD.md
    └── BOOTSTRAP_ALGORITHM_EXAMPLE.py
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

### API Integration (`scripts/data.py`)
- Helius API for transaction data
- Cielo API for P&L data
- Data caching in DuckDB

### Analysis Engine
- `harsh_insights.py`: Generates brutal, actionable insights
- `instant_stats.py`: Quick baseline statistics
- `blind_spots.py`: Behavioral pattern detection
- `analytics.py`: Statistical calculations

### Deep Analysis (`src/walletdoctor/`)
- Advanced pattern detection with statistical validation
- Psychological mapping of trading behaviors
- Confidence scoring system

## Database Schema

### DuckDB Tables
- `tx`: Transaction data from Helius
- `pnl`: Profit/loss data from Cielo
- `trade_annotations`: User notes on trades
- `trade_snapshots`: Historical snapshots

## Environment Variables

Required for deployment:
- `HELIUS_KEY`: Helius API key for transaction data
- `CIELO_KEY`: Cielo API key for P&L data
- `OPENAI_API_KEY`: OpenAI key for AI insights (optional)

## Deployment

Deployed on Railway with automatic builds from GitHub pushes. See `DEPLOY_TO_RAILWAY.md` for details. 