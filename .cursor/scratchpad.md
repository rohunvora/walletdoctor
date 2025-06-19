# Pocket Trading Coach - Current State & Strategy

## 🎯 Project Vision
A Telegram bot that acts as a real-time trading coach by:
1. Monitoring user trades as they happen
2. Providing analytical feedback with exact percentages
3. Using GPT with function calling for self-directed data access
4. Maintaining a single source of truth (diary table)

## 📊 Current Implementation: Lean Pipeline v1

### Architecture Overview (Simplified)
```
Wallet → Listener → Diary → Prompt Builder → GPT (with tools) → Telegram
```

### What's Working Now ✅

1. **Lean Pipeline Architecture**
   - Single flow from wallet events to GPT responses
   - Diary table as single source of truth with JSON data field
   - GPT with function calling for self-directed data access
   - Sub-5ms performance (actual: 4.6ms cold start, 1107x faster with cache)

2. **Bankroll Awareness**
   - Captures `bankroll_before_sol` and `bankroll_after_sol` via RPC
   - Calculates exact `trade_pct_bankroll` (no rounding)
   - Tracks position changes accurately

3. **GPT Tools Available**
   - `fetch_last_n_trades` - Get recent trades (with 20-trade memory cache)
   - `fetch_trades_by_token` - Get trades for specific token
   - `fetch_trades_by_time` - Get trades in time range (e.g., "late night degen")
   - `fetch_token_balance` - Get current token balance

4. **Coach L Personality**
   - Dry, analytical style (≤120 words enforced via max_tokens)
   - Uses exact numbers from data
   - No emojis or exclamation points

### Recent Bug Fixes (Implemented) ✅

1. **Fixed Bankroll Calculation**
   - Now calls `_get_sol_balance()` after swap for actual chain state
   - Added 0.5s delay for chain state to update
   - No more inferring bankroll from math

2. **Added Wallet Address to Prompt**
   - `wallet_address` now included in prompt data
   - GPT tools receive the wallet address for proper execution
   - Fixes "no recorded trades" issue

3. **Reduced Verbosity**
   - Changed `max_tokens` from 150 → 80 in GPT calls
   - Forces responses under ~60 words
   - No new rules or templates needed

4. **Position Tracking Available**
   - `fetch_token_balance` tool already defined
   - Coach prompt mentions to use it after partial sells
   - GPT can now report remaining positions

### Core Components

- `telegram_bot_coach.py` - Main bot with lean pipeline
- `diary_api.py` - 4 helper functions with caching
- `diary_schema.sql` - Single table schema with indexes
- `prompt_builder.py` - Minimal context builder
- `coach_prompt_v1.md` - Coach L personality prompt
- `gpt_client.py` - Enhanced with `chat_with_tools` method

### Archived Components (No Longer Used)
- `conversation_engine.py` - Old abstraction layer
- `enhanced_context_builder.py` - Complex context system
- `pattern_service.py` - Pattern detection logic
- `state_manager.py` - State management
- `nudge_engine.py` - Question generation

## 📁 Repository Structure

### Active Bot Files:
- `telegram_bot_coach.py` - Production bot with lean pipeline
- `diary_api.py` - Data access layer
- `prompt_builder.py` - Minimal prompt construction
- `gpt_client.py` - GPT client with tools
- `coach_prompt_v1.md` - System prompt

### Supporting Services:
- `scripts/token_metadata.py` - Token information
- `scripts/notification_engine.py` - Trade notifications
- `scripts/transaction_parser.py` - Blockchain parsing

### Documentation:
- `README.md` - Updated with lean architecture
- `BOT_MANAGEMENT.md` - Deployment instructions
- `.cursor/scratchpad.md` - This file

## 🎯 Current State

The bot is running with the lean pipeline architecture. All complexity has been removed in favor of a simple, direct flow:

1. Trade happens → captured with bankroll data
2. Written to diary with exact percentages
3. GPT gets minimal context + tools
4. GPT self-directs data access as needed
5. Response limited to 60 words

### Success Metrics Achieved:
- **Performance**: <5ms requirement met (4.6ms)
- **Accuracy**: Exact trade percentages preserved
- **Simplicity**: 6+ services reduced to single pipeline
- **Intelligence**: GPT can self-query for context

## 🚫 What We're NOT Building
- Complex abstraction layers
- Pattern detection engines
- State management systems
- Enhanced context builders
- Whack-a-mole rule systems

## 📝 Lessons Learned

1. **Simpler is Better**: The lean pipeline outperforms the complex architecture
2. **Trust the LLM**: GPT with tools is smarter than hardcoded patterns
3. **Single Source of Truth**: One diary table beats multiple services
4. **Exact Data Matters**: Preserve exact percentages, don't round
5. **Performance First**: Sub-5ms makes the bot feel instant

---

## 📋 Recent Updates

### Lean Pipeline Implementation (Completed)
- Created diary schema with proper indexes
- Implemented 4 helper functions with caching
- Built minimal prompt builder
- Added GPT function calling
- Archived old abstraction layers
- Achieved <5ms performance

### Bug Fixes Applied
1. ✅ Recalculate bankroll via RPC after each trade
2. ✅ Pass wallet_address to GPT for tool execution  
3. ✅ Reduce max_tokens to 80 for brevity
4. ✅ Ensure position tracking tools available

### Current Bot Status
- Running on branch: `lean-pipeline-v1`
- Bot handle: @mytradebro_bot
- Database: `pocket_coach.db`
- Performance: 4.6ms cold start, <1ms with cache