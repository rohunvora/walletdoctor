# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Bot Management
```bash
# Start the bot
./management/start_bot.sh

# Stop the bot
./management/stop_bot.sh

# Check bot status
./management/status_bot.sh

# Restart the bot
./management/restart_bot.sh
```

### Testing
```bash
# Run all unit tests
python3 -m pytest tests/

# Run specific test file
python3 test_bot_scenarios.py
python3 test_analytics_cutover.py
python3 test_lean_pipeline.py

# Run tests in a directory
python3 -m pytest tests/unit/
```

### Setup and Configuration
```bash
# Configure API keys interactively
python3 setup.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture Overview

### Core Pipeline
The bot follows a goal-oriented coaching pipeline:
```
Wallet → Trades → Diary → Goal Context → GPT → Coaching
```

### Key Components

1. **Main Bot Entry Point** (`telegram_bot_coach.py`)
   - Handles Telegram interactions
   - Monitors trades and sends notifications
   - Integrates analytics for intelligent responses
   - Supports two prompt versions (v1: brief, v2: intelligent assistant)

2. **Analytics System**
   - `event_store.py`: Event storage in SQLite for fast queries
   - `aggregator.py`: Python-based calculations (not GPT)
   - `diary_api.py`: Analytics tools for temporal queries
   - Performance target: <10ms queries, <200ms end-to-end

3. **AI Integration**
   - `gpt_client.py`: OpenAI client with timeout handling
   - `prompt_builder.py`: Constructs context from goals, trades, and analytics
   - System prompts: `coach_prompt_v1.md` (brief) and `coach_prompt_v2.md` (intelligent)

4. **Data Layer**
   - DuckDB for main data storage
   - SQLite for event store (analytics)
   - Dual-write pattern during migration phase

### Design Principles

- **Natural Conversation**: No commands, just chat
- **Goal-Oriented**: Every response filtered through user objectives
- **Deterministic Analysis**: Python calculations, not GPT approximations
- **Simple Pipeline**: Direct flow without complex abstractions
- **Performance-Focused**: Sub-200ms response times

### Current Development Focus

The project is transitioning from v1 (simple trade acknowledger) to v2 (intelligent assistant) behavior:
- v2 adds proactive position sizing advice
- v2 includes pattern recognition and behavioral insights
- Analytics cutover is complete (Phase 5)
- Testing framework includes comprehensive scenario coverage

### Important Notes

- No linting or formatting tools are configured
- Tests should be run before committing changes
- The bot operates on the Solana blockchain
- All sensitive data (API keys) must be in `.env` file
- Database files are local and not committed to git