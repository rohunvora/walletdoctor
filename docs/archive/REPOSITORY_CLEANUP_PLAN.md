# Repository Cleanup Plan

## Current State Analysis

The repository contains two distinct products that have been conflated:

1. **Tradebro** (`telegram_bot_simple.py`) - Harsh wallet analysis bot
   - Analyzes historical trades
   - Provides brutal insights
   - One-time analysis tool

2. **Pocket Trading Coach** (`telegram_bot_coach.py`) - Real-time coaching bot
   - Monitors live trades
   - Asks conversational questions
   - Builds memory over time

## Cleanup Actions

### 1. Clarify Product Separation
- [ ] Update README to clearly distinguish between the two bots
- [ ] Create separate sections for each product
- [ ] Add clear use case descriptions

### 2. Database Consolidation
- [ ] Remove duplicate database files:
  - Keep: `pocket_coach.db` (production for coach bot)
  - Remove: `coach.db` (old version)
  - Remove: `wallet_coach.db` (unclear purpose)
- [ ] Document which database is used by which bot

### 3. Documentation Cleanup
- [ ] Consolidate overlapping docs:
  - Keep: README.md, BOT_MANAGEMENT.md, TESTING_GUIDE.md
  - Archive to `docs/archive/`: Historical implementation docs
  - Update: PROJECT_STRUCTURE.md to reflect current state
- [ ] Remove outdated references to deprecated features

### 4. Code Organization
- [ ] Move web interface files to separate directory:
  - `web/` directory for web_app_v2.py and related files
- [ ] Keep bot files in root for clarity
- [ ] Ensure scripts/ contains only shared utilities

### 5. Test Cleanup
- [ ] Review tests/ directory for relevance
- [ ] Remove tests for deleted features
- [ ] Add tests for state management system

### 6. Configuration Cleanup
- [ ] Update env.example with all required variables
- [ ] Remove Railway deployment files if not using Railway
- [ ] Ensure .gitignore covers all generated files

## Proposed Structure

```
walletdoctor/
├── README.md                    # Clear product descriptions
├── telegram_bot_coach.py        # Pocket Trading Coach
├── telegram_bot_simple.py       # Tradebro analyzer
├── state_manager.py            # Coach bot state management
├── pattern_service.py          # Coach bot patterns
├── nudge_engine.py            # Coach bot nudges
├── conversation_manager.py     # Coach bot conversations
├── pocket_coach.db            # Production database
├── bot.log                    # Current log file
├── scripts/                   # Shared utilities
│   ├── pnl_service.py
│   ├── price_service.py
│   ├── token_metadata.py
│   └── ...
├── web/                       # Web interface (separate product)
│   ├── web_app_v2.py
│   ├── templates_v2/
│   └── wsgi_v2.py
├── docs/                      # Active documentation
│   ├── CONTEXT_AWARE_AI_PLAN.md
│   └── archive/              # Historical docs
├── management/               # Bot management scripts
│   ├── start_bot.sh
│   ├── stop_bot.sh
│   └── status_bot.sh
├── tests/                    # Updated test suite
├── .cursor/                  # Cursor workspace
│   └── scratchpad.md        # Internal documentation
├── requirements.txt
├── env.example
├── LICENSE
└── .gitignore
```

## Implementation Steps

1. **Backup First**
   ```bash
   git add -A
   git commit -m "Pre-cleanup backup"
   git tag pre-cleanup
   ```

2. **Create Directories**
   ```bash
   mkdir -p web docs/archive management
   ```

3. **Move Files**
   ```bash
   # Move web files
   mv web_app_v2.py wsgi_v2.py web/
   mv templates_v2 web/
   
   # Move management scripts
   mv start_bot.sh stop_bot.sh status_bot.sh restart_bot.sh management/
   
   # Archive old docs
   mv docs/TEXT_FIRST_IMPLEMENTATION.md docs/archive/
   # ... (other historical docs)
   ```

4. **Remove Deprecated Files**
   ```bash
   rm coach.db wallet_coach.db
   rm -rf __pycache__ scripts/__pycache__
   ```

5. **Update References**
   - Update import paths in moved files
   - Update documentation references
   - Update shell scripts with new paths

6. **Test Everything**
   ```bash
   python telegram_bot_coach.py  # Test coach bot
   python telegram_bot_simple.py # Test analyzer bot
   python web/web_app_v2.py      # Test web interface
   ```

## Success Criteria

- [ ] Clear separation between products
- [ ] No duplicate or unclear files
- [ ] All imports working correctly
- [ ] Documentation reflects reality
- [ ] Repository is easy to navigate
- [ ] New contributors can understand structure

## Notes

- Keep both bots as they serve different valuable purposes
- Prioritize clarity over perfect organization
- Document everything that isn't obvious
- Test after each major change 