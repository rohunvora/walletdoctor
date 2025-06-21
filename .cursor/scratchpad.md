# Pocket Trading Coach - Goal-Oriented System

## 🎯 Current Vision
Build a trading coach that helps users achieve their specific goals through natural conversation with zero jankiness.

**Core Insight**: The payoff loop - users log facts → bot stores them → bot uses them when relevant → users see value → users log more.

## 🏗️ Architecture

### Current Implementation (Working)
```
Wallet → Listener → Diary → Prompt Builder → GPT (with tools) → Telegram
```

- **Lean Pipeline**: Single flow, no abstraction layers
- **Performance**: <5ms cold start, <200ms end-to-end with APIs
- **Data**: Single diary table as source of truth
- **Intelligence**: GPT with self-directed tool access

### Active Components
- `telegram_bot_coach.py` - Main bot
- `diary_api.py` - Data layer (4 functions)
- `prompt_builder.py` - Context builder
- `gpt_client.py` - GPT with tools
- `coach_prompt_v1.md` - System prompt

### Bot Status
- Bot handle: @mytradebro_bot
- Database: `pocket_coach.db`
- Performance: 4.6ms cold start

---

## 🚀 ACTIVE DEVELOPMENT: Goal-Oriented Adaptive Coach

### ✅ Phase 1+2: Foundation + Onboarding (COMPLETED - Dec 2024)

#### What Was Implemented:
1. **Database Schema** ✅
   - Created `user_goals` table with flexible JSON storage
   - Created `user_facts` table for open-ended fact storage
   - Added indexes for efficient queries

2. **GPT Tools** ✅
   - Added `save_user_goal` function for goal extraction
   - Added `log_fact` function for remembering user details
   - Integrated into GPT client's chat_with_tools method

3. **System Prompt Updates** ✅
   - Added goal understanding principles
   - Natural onboarding instructions
   - Contextual judgment guidelines
   - Fact storage guidance

4. **Context Enhancement** ✅
   - Added user_goal to prompt context
   - Added recent_facts list
   - Added trade_sequence with timing gaps
   - Included user_id for tool execution

5. **Removed Fixed Thresholds** ✅
   - Eliminated price_alert thresholds
   - Removed template responses
   - Trust GPT intelligence for contextual decisions

#### Next Steps:
1. **Test the Implementation**
   - Connect a wallet and test natural goal extraction
   - Verify facts are being stored correctly
   - Check that goals influence coaching feedback

2. **Monitor & Refine**
   - Observe how GPT handles ambiguous goals
   - See if fact storage is too aggressive or too passive
   - Adjust system prompt based on actual usage

3. **Phase 3: Let Intelligence Emerge**
   - Watch for patterns in how GPT uses goals/facts
   - Add context data as needed (not features)
   - Refine based on real user interactions

### Implementation Notes:
- Migration script: `db_migrations.py`
- Run with: `python db_migrations.py` (in venv)
- Bot needs restart to pick up new tools
- Goals stored as JSON for maximum flexibility
- Facts use key-value pairs with usage tracking

### Testing Commands:
```
# Run migration
source venv/bin/activate
python db_migrations.py

# Restart bot
./management/stop_bot.sh
./management/start_bot.sh

# Test goal extraction
"trying to get to 1k sol"
"need to make $500 this week"
"want 80% win rate"

# Test fact storage
"I only trade at night"
"lost big on BONK last week"
"need $800 for rent"
```

### Principles Going Forward
1. **Data > Templates**: Pass raw data, trust GPT
2. **Primitives > Categories**: Simple storage, intelligent retrieval  
3. **Natural > Structured**: Conversation drives everything
4. **Flexible > Rigid**: Expect and handle ambiguity

---

## 📋 System Prompt Updates

### Core Principles (Not Rules)
- Understand goals from natural language
- Calculate progress using available data
- Decide when to speak based on significance to user
- Store facts that seem important for later

### Remove These Lines
```markdown
- ONLY speak if trade impact > 10% of goal progress
- ONLY speak if position size > 25% of bankroll
```

### Add These Concepts
```markdown
## Contextual Judgment

You have access to:
- User's stated goal (if any)
- Their trading history
- Current trade details

Use judgment to decide when to comment. Consider:
- Is this unusual for them?
- Does it significantly impact their goal?
- Have they been doing this repeatedly?
- Would silence be more valuable?

## Natural Progress Tracking

When users have goals, weave progress naturally:
- "puts you at 180 SOL" not "18% progress"
- "that's a week of profits" not "7.2% of monthly target"
- "getting closer" not "on track"
```

---

## 📊 Success Metrics (Revised)
- **Natural conversations**: No "command not recognized" errors
- **Goal emergence**: Goals extracted from normal chat, not forms
- **Contextual interventions**: Comments feel relevant, not rule-based
- **Fact utility**: Stored facts get referenced naturally later

---

## 📁 Archived Work

### Completed Features
- ✅ Lean Pipeline Architecture
- ✅ P&L Integration (Cielo API)
- ✅ Market Cap Intelligence
- ✅ Price History (1-min snapshots)
- ✅ Peak Alerts (3x, 5x, 10x)
- ✅ GPT Tools (8 functions)

### Archived Components
- `conversation_engine.py` - Old abstraction layer
- `enhanced_context_builder.py` - Complex context system
- `pattern_service.py` - Pattern detection logic
- `state_manager.py` - State management
- `nudge_engine.py` - Question generation

### Key Lessons
1. Simpler is better - lean pipeline outperforms complex architecture
2. Trust the LLM - GPT with tools beats hardcoded patterns
3. Single source of truth - one diary table beats multiple services
4. Performance first - sub-5ms makes bot feel instant

---

## 🎯 Project Vision
A Telegram bot that acts as a real-time trading coach by:
1. Monitoring user trades as they happen
2. Providing analytical feedback with exact percentages
3. Using GPT with function calling for self-directed data access
4. Maintaining a single source of truth (diary table)
5. **NEW**: Learning and adapting to user preferences over time

## 📊 Current Implementation: Lean Pipeline v1.1

### Architecture Overview
```
Wallet → Listener → Diary → Prompt Builder → GPT (with tools) → Telegram
                       ↓                         ↑
                  Preferences ←←←←←←←←←←←←←←← (NEW: Two-way flow)
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
- **Market Cap Awareness**: All trades now tracked with market cap context
- **P&L Integration**: Cielo data integrated for accurate profit/loss tracking

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
6. **Use External APIs**: Cielo for P&L, DexScreener for market caps - don't reinvent

---

## 📋 Recent Updates (December 2024)

### ✅ Lean Pipeline Implementation (Completed)
- Created diary schema with proper indexes
- Implemented 4 helper functions with caching
- Built minimal prompt builder
- Added GPT function calling
- Archived old abstraction layers
- Achieved <5ms performance

### ✅ P&L Integration (Completed)
- SELL trades now fetch Cielo P&L data
- Added `fetch_wallet_stats` and `fetch_token_pnl` tools
- Coach can answer "What's my win rate?" and "Did I profit?"
- Includes historical data from before bot usage

### ✅ Market Cap-Centric Trading (Completed)
- All trades capture market cap at time of trade
- SELL notifications show multiplier from entry: "2.7x from $2M entry"
- New GPT tool: `fetch_market_cap_context`
- Coach now thinks in trader language: "buying at $4M? Easy money was at $400K"

### ✅ Multiple Buys / DCA Support (Completed)
- Uses Cielo's average buy price for accurate entry calculations
- Estimates average entry market cap from price ratios
- Shows "avg entry" in notifications when multiple buys detected
- Handles pre-bot trading history automatically

### Current Bot Status
- Running on branch: `lean-pipeline-v1`
- Bot handle: @mytradebro_bot (@mywalletdoctor_bot is WRONG bot)
- Database: `pocket_coach.db`
- Performance: 4.6ms cold start, <1ms with cache

---

## 📊 Current Capabilities

### What the Bot Can Do Now:

1. **Real-time Trade Monitoring**
   - Monitors Solana wallets for swaps
   - Captures exact trade percentages of bankroll
   - Tracks market cap at entry and exit
   - Shows P&L on exits with Cielo integration

2. **Market Cap Intelligence**
   - "Bought BONK at $1.2M mcap (0.5 SOL)"
   - "Sold WIF at $5.4M mcap (2.7x from $2M avg entry) +$230"
   - Risk/reward analysis based on market cap tiers

3. **P&L Tracking**
   - Overall win rate and total P&L
   - Token-specific profit/loss data
   - Handles multiple buys with weighted averages
   - Includes pre-bot trading history

4. **GPT Tools Available**
   - `fetch_last_n_trades` - Recent trades
   - `fetch_trades_by_token` - Token-specific history
   - `fetch_trades_by_time` - Time-based analysis
   - `fetch_token_balance` - Current holdings
   - `fetch_wallet_stats` - Overall statistics
   - `fetch_token_pnl` - Token P&L data
   - `fetch_market_cap_context` - Market cap analysis

5. **Coach L Personality**
   - Blunt, analytical feedback
   - Market cap-aware commentary
   - Sub-60 word responses
   - Uses exact data from tools

### What's Still Missing:

1. **Goal-Aware Coaching**
   - No goal extraction from conversation
   - No progress tracking toward objectives
   - No personalized interventions
   - No fact memory system

2. **Enhanced Context**
   - Limited timing data between trades
   - No USD values alongside SOL
   - Missing price momentum data
   - No session-level aggregations

3. **Behavioral Understanding**
   - No insight into trade sequences
   - Missing timing-based context
   - No unusual behavior detection
   - Limited historical comparisons

4. **Progress Insights**
   - No period-over-period analysis
   - Missing improvement indicators
   - No contextual benchmarks
   - Limited long-term view

---

## 🎯 Next Priorities

### Priority 1: Goal System Implementation (High Impact, Clear Path)
**Why**: Core value prop - personalized coaching
- Natural goal extraction from conversation
- Flexible fact storage system
- Progress tracking without rigid formulas
- Trust GPT to understand context

### Priority 2: Enhanced Context Data (High Impact, Low Effort)
**Why**: Better data enables better insights
- Add SOL price for USD context
- Include trade timing sequences
- Pass recent P&L patterns
- Let GPT identify what matters

### Priority 3: Behavioral Insights (Medium Impact, Natural Emergence)
**Why**: Help users understand their habits
- Provide timing and outcome data
- Let GPT notice patterns naturally
- No predetermined categories
- Focus on what's unusual for each user

### Priority 4: Progress Understanding (Medium Impact, User Value)
**Why**: "Am I improving?" is universal
- Historical comparison data
- Let GPT frame progress naturally
- No fixed metrics or timeframes
- Contextual to user's goals

---

## 🏗️ Technical Debt & Improvements

### Immediate Fixes Needed:
1. **Wrong Bot Token**: .env has token for @mywalletdoctor_bot, need @mytradebro_bot
2. **Error Handling**: Some edge cases need better error recovery
3. **Testing**: Need automated tests for core functionality

### Architecture Improvements:
1. **Modularize Services**: Break out P&L, market cap, price services
2. **Better Caching**: Implement Redis for cross-process cache
3. **Webhook Support**: Move from polling to webhooks for trades

### Documentation Needs:
1. **API Documentation**: Document all GPT tools
2. **Deployment Guide**: Update for new dependencies
3. **Testing Guide**: How to test market cap features

---

## 🚀 Vision: Where We're Heading

The Pocket Trading Coach should become the trader's intelligent companion that:

1. **Understands Your Goals**: Helps you achieve what YOU want
2. **Speaks Your Language**: Market caps, multipliers, risk/reward
3. **Keeps You Honest**: Contextual feedback based on your history
4. **Shows Your Progress**: Frames improvement in your terms
5. **Prevents Disasters**: Warns when behavior threatens your goals

We're building the coach that adapts to each trader's unique journey.

---

## 🔮 Future Vision

The Pocket Trading Coach evolving into an adaptive, personalized trading companion:

1. **Learns Your Style**: Adapts to your unique patterns
2. **Remembers Everything**: Facts and preferences persist naturally
3. **Evolves With You**: Gets smarter about your specific context
4. **Contextual Awareness**: Understands when to speak and when to stay quiet
5. **Natural Intelligence**: No rigid rules, just understanding

Next Decision Point: Ready to implement Phase 1+2 with this primitives-first approach? ✅ COMPLETED

Current Status: Phase 1+2 implemented and pushed. Ready for testing and Phase 3 emergence.