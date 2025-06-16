# Pocket Trading Coach - Current State & Strategy

## 🎯 Project Vision
A Telegram bot that acts as a real-time trading coach by:
1. Monitoring user trades as they happen
2. Asking context-aware questions based on patterns
3. Remembering conversations to build understanding
4. Helping traders recognize their own behavioral patterns

## 📊 Current Implementation Status

### What's Built and Working:
1. **Real-time Trade Monitoring** ✅
   - Detects trades within 5 seconds via `telegram_bot_coach.py`
   - Monitors user wallets with personalized tracking
   - Integrates with Pump.fun, Raydium, and other DEXes

2. **Pattern Detection** ✅
   - Repeat token tracking (warns on repeated failures)
   - Position size analysis (alerts on oversized trades)
   - Hold time patterns (identifies optimal exit windows)
   - Immediate patterns (dust trades, round numbers, late night)

3. **State-Based Memory** ✅
   - Token notebooks track conversation state per token
   - Open questions queue prevents duplicate questions
   - Persistent storage survives bot restarts
   - Per-user isolation for privacy

4. **P&L-Aware Responses** ✅
   - Integrated Cielo Finance for accurate P&L
   - Different templates for profits vs losses
   - Context-aware questions based on position performance

### Current Problems:
1. **Bot Still Feels Dumb** - Rigid rules can't understand context
2. **Wrong Classifications** - "Cut the position" while UP gets tagged as "stop loss"
3. **P&L Accuracy Issues** - Sometimes shows incorrect profit numbers
4. **Pointless Callbacks** - Quotes user from "0 minutes ago"

## 🏗️ Architecture Overview

```
User Wallet → Real-time Monitor → Pattern Service → State Manager → Nudge Engine → Telegram
                    ↓                                    ↓
              DuckDB Storage                    Token Notebooks
```

### Key Components:
- `telegram_bot_coach.py` - Main bot with commands and monitoring
- `state_manager.py` - Conversation state and memory management
- `pattern_service.py` - Detects trading patterns and behaviors
- `nudge_engine.py` - Generates contextual questions/nudges
- `scripts/pnl_service.py` - P&L data from Cielo/Birdeye

## 🚀 Next Step: Context-Aware AI Layer

### The Problem:
Each bug fix adds more if/else complexity without solving the core issue - the bot doesn't actually understand what's happening, it just follows rules.

### Proposed Solution:
Build a context-aware AI layer that:
1. **Understands Intent** - "Cut the position" means different things when up vs down
2. **Tracks Conversation Flow** - Knows what was discussed and when
3. **Generates Natural Responses** - Not just template selection
4. **Learns User Patterns** - Adapts to individual trading styles

### Implementation Approach:
1. **Context Packs** - Bundle trade data, conversation history, and user patterns
2. **LLM Integration** - Use GPT-4 for understanding, not just templates
3. **Thin Slice First** - Start with classification (stop loss vs profit taking)
4. **Gradual Expansion** - Add more intelligence incrementally

## 📁 Repository Structure

### Core Bot Files:
- `telegram_bot_coach.py` - Production bot with state management
- `state_manager.py` - Conversation state and memory
- `pattern_service.py` - Pattern detection logic
- `nudge_engine.py` - Question/nudge generation
- `conversation_manager.py` - User interaction handling

### Supporting Services:
- `scripts/pnl_service.py` - P&L data integration
- `scripts/personal_history.py` - User trading history
- `scripts/token_metadata.py` - Token information
- `scripts/price_service.py` - Price data and caching

### Web Interface (Separate Product):
- `web_app_v2.py` - Web-based wallet analysis
- `telegram_bot_simple.py` - Original simple bot (deprecated?)

### Documentation:
- `README.md` - User-facing documentation
- `.cursor/scratchpad.md` - This file, internal state tracking
- Various docs in `docs/` - Historical implementation notes

## 🎯 Strategic Direction

### Immediate Priority:
Before adding AI complexity, we need to:
1. **Clean up the repository** - Remove deprecated files
2. **Consolidate documentation** - Single source of truth
3. **Fix known bugs** - P&L accuracy, classification issues
4. **Establish clear architecture** - What each component does

### Then Build Context Layer:
1. **Start Small** - Just improve stop loss vs profit taking classification
2. **Use Existing Data** - Context packs from current state manager
3. **Test Thoroughly** - Ensure it actually improves user experience
4. **Iterate Based on Feedback** - Let users guide development

### Success Metrics:
- **Accuracy**: Correct classification of user intent
- **Relevance**: Questions that make sense in context
- **Engagement**: Users actually answer the questions
- **Behavior Change**: Measurable improvement in trading

## 🚫 What We're NOT Building
- Whale tracking systems
- Copy trading features
- Price predictions
- Market analysis
- Generic trading advice
- Web dashboards (until bot is perfect)

## 📝 Technical Debt to Address
1. Multiple database files (consolidate to one)
2. Two telegram bots (deprecate simple version?)
3. Scattered documentation (consolidate to README + this file)
4. Test coverage (many tests but unclear what's tested)
5. Error handling (some edge cases not covered)

## 🔄 Next Actions
1. Clean up repository structure
2. Update README with accurate current state
3. Document the context-aware AI approach
4. Create implementation plan for AI layer
5. Begin with thin slice: intent classification 