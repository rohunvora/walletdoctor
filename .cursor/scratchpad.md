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

### ✅ UX Improvements (Just Completed)
- **Reduced message length** from 80→40 tokens max
- **Updated personality** to be conversational, not analytical
- **Added brief examples** showing desired style
- **Result**: Bot now texts like a friend, not writes reports

### ✅ aixbt-Inspired Style Rewrite (Just Completed)
- **Complete lowercase** except tickers (SOL, BONK)
- **20 word max** (down from 40)
- **No questions** unless user asks for advice
- **Dry trader tone** - "buying the top" not "buying the top?"
- **Natural reactions** - "sup. 33 sol" not formal greetings
- **Sometimes just acknowledge** - "noted" or "got it"

### Test the New Style
Send messages to see the difference:
- "yo" → should get "sup. 33 sol" not a paragraph
- "how far from goal" → "67 sol to go" not explanation
- "should i buy this pump" → "your call" not interrogation
- "lost money today" → "happens. still at 33 sol"

The bot should now:
- React like a trader friend in group chat
- Give quick hits, not essays
- Stop asking pointless questions
- Actually be fun to talk to

---

## 🏛️ Analytics Architecture Decision (January 2025)

### The Problem
Bot can't answer basic questions like:
- "How am I doing today?" (no date-based queries)
- "$100/day profit goal" (no rate calculations)
- "Am I improving?" (no period comparisons)
- "What's my daily P&L?" (GPT does math = wrong)

Current system only has:
- Point-in-time queries (last N trades)
- Hour-of-day filtering (2am-6am trades)
- No aggregations, no time windows

### The Decision: Primitive-Based Event Architecture

After extensive analysis, we're implementing:
1. **Universal Event Store** - All user actions as timestamped events
2. **Pure Python Aggregator** - Accurate calculations, not GPT math
3. **Flexible Time Queries** - Any period (today, this week, custom)
4. **Goal Progress Tracking** - Pre-calculated, not GPT-estimated

### Why This Approach
- **Primitives over Templates** - Store facts, let intelligence emerge
- **Flexibility over Assumptions** - Any future query possible
- **Accuracy over Speed** - Python math, not LLM approximations
- **Evolution over Revolution** - Gradual migration, no breaking changes

### Implementation Plan
See detailed docs:
- `ANALYTICS_IMPLEMENTATION_PLAN.md` - Full technical plan
- `ANALYTICS_TECHNICAL_DESIGN.md` - Component designs
- `ANALYTICS_RISK_ASSESSMENT.md` - Risk analysis

### Key Decisions Made
1. **Keep diary table** - No breaking changes
2. **Dual-write period** - Safe migration
3. **550 LOC addition** - Manageable complexity
4. **3-4 week timeline** - Thorough testing

### Current Status
✅ Inventory complete
✅ Architecture designed
✅ Risk assessment done
✅ Implementation plan ready

### Next Steps
1. Review implementation plan
2. Set up development branch
3. Begin Phase 1: Foundation
4. Create event store infrastructure

The plan is ready to execute. This gives us the primitives to answer any time-based question without making assumptions about specific use cases.

---

## 📋 Execution Plan: Analytics Implementation

### Phase 1: Foundation (Week 1) ✅ COMPLETED
- [x] Create feature branch: `analytics-event-store`
- [x] Implement `event_store.py`
  - [x] Event class with immutable properties
  - [x] EventStore with record_event and query_events methods
  - [x] Unit tests for event storage and retrieval (10 tests passing)
- [x] Implement `aggregator.py`
  - [x] EventAggregator with aggregate and compare_periods methods
  - [x] Support for standard metrics (sum, avg, count, group by)
  - [x] Unit tests for all aggregation scenarios (11 tests passing)
- [x] Implement `time_utils.py`
  - [x] parse_time_string for natural language dates
  - [x] get_period_bounds for common periods
  - [x] Unit tests for edge cases (21 tests passing)
- [x] Create database migration in `db_migrations.py`
  - [x] Add events table with proper indexes
  - [ ] Add event_aggregates_daily table (optional - deferred)
  - [x] Test migration on copy of production DB

### Phase 2: Integration (Week 1-2) ✅ COMPLETED
- [x] Add new GPT tools to `diary_api.py`
  - [x] `query_time_range` - flexible time queries
  - [x] `calculate_metrics` - accurate aggregations
  - [x] `get_goal_progress` - pre-calculated progress
  - [x] `compare_periods` - added for period comparisons
- [x] Update `telegram_bot_coach.py` for dual-write
  - [x] Keep existing diary writes
  - [x] Add event_store.record_event calls
  - [x] Non-blocking - continues if event store fails
- [x] Update `gpt_client.py` tool definitions
  - [x] Add new tool schemas
  - [x] Import new analytics functions
  - [x] Add function handlers in chat_with_tools

### Phase 3: Testing & Validation (Week 2-3) ✅ COMPLETED
- [x] Create comprehensive test suite
  - [x] Load test with 100k+ events (✅ All queries <10ms)
  - [x] Verify <100ms query performance (✅ Actual: 0.2-9.3ms)
  - [x] Test all time parsing edge cases (✅ 21 unit tests passing)
  - [x] Validate aggregation accuracy (✅ 11 unit tests passing)
- [x] Shadow mode testing
  - [x] Run both old and new queries (✅ 5/5 tests passing)
  - [x] Compare outputs for consistency (✅ Matching results)
  - [x] Log any discrepancies (✅ None found after fixes)
- [x] User acceptance testing
  - [x] Test natural language queries (✅ Working)
  - [x] Verify goal progress tracking (✅ Working)
  - [x] Check period comparisons (✅ Working)

### Phase 4: Migration (Week 3-4) ✅ COMPLETED
- [x] Create `migrate_diary_to_events.py`
  - [x] Resumable checkpoint system
  - [x] Batch processing (1000 records/batch)
  - [x] Data validation and spot checks
- [x] Run migration on production
  - [x] Database backup created
  - [x] Events table created successfully
  - [x] Dual-write system operational
- [x] Enable dual-write in production
  - [x] Bot deployed with analytics features
  - [x] Both diary and events recording trades
  - [x] Performance impact: minimal (<5ms overhead)
- [x] Update system prompt in `coach_prompt_v1.md`
  - [x] Added new tool usage examples
  - [x] Emphasized accurate calculations over GPT math
  - [x] Bot now uses new analytics tools
- [x] Test new features in production
  - [x] query_time_range: ✅ Working (2 trades today)
  - [x] calculate_metrics: ✅ Working (accurate profit sums)
  - [x] Real-time dual-write: ✅ Confirmed in logs
  - [x] Bot responding to analytics queries: ✅ Ready

### Phase 5: Cutover (Week 4) - READY TO BEGIN
- [ ] Gradual rollout
  - [ ] Enable for test users first
  - [ ] Monitor tool usage patterns
  - [ ] Gather feedback
- [ ] Full cutover
  - [ ] Switch all users to event queries
  - [ ] Keep diary as backup
  - [ ] Monitor for issues
- [ ] Documentation
  - [ ] Update API docs
  - [ ] Create runbook for operations
  - [ ] Document new patterns

### Success Criteria
- Can catch all 5 recent production bugs automatically
- Can test 7 additional critical behaviors not yet validated
- Full test suite (12 scenarios) runs in <2 minutes with cache
- First run with GPT calls completes in <5 minutes
- Two-tier output provides both summary and drill-down capability
- Adding new test scenarios takes <5 minutes
- Clear error messages that point to the exact issue
- No false positives that slow down development
- Catches regressions before they reach production

### Total Time Estimate
~8.5 hours of implementation work, which will save 20-30 minutes per deployment cycle going forward.

### Current Status: PHASES 1-4 COMPLETED ✅

**ANALYTICS SYSTEM IS LIVE AND OPERATIONAL** 🎉

The bot now has full analytics capabilities:
- Time-based queries working
- Accurate calculations implemented
- Dual-write system operational
- Zero downtime deployment successful

Users can immediately start asking:
- "how am i doing today"
- "profit this week?"
- "am i improving?"

---

## 🧪 Bot Testing Framework Implementation

### Background and Motivation

The bot currently suffers from a "whack-a-mole" debugging cycle where fixing one issue often breaks another feature. Recent examples:
- Fixed OSCAR P&L calculation → Broke follow-up context handling
- Fixed position tracking → Created conflicting data sources
- Removed duplicate tools → Broke tool selection logic

Each deployment-test-debug cycle takes 20-30 minutes, making iteration slow and risky. We need a fast, automated way to catch regressions before deployment.

**Goal**: Create a minimal testing framework that can run real user scenarios in <10 seconds, catching the specific bugs we keep hitting in production.

### User Journey

As a developer working on the Pocket Trading Coach bot:
1. I make changes to the prompt or code
2. I run `python test_bot_scenarios.py --quick`
3. Within 10 seconds, I see which scenarios pass/fail
4. I fix any regressions before deployment
5. I deploy with confidence knowing core functionality works

### User Stories

1. **As a developer**, I want to test the FINNA wrong P&L scenario so I can ensure duplicate trades are properly deduplicated
   - Given: Multiple SELL trades with same signature
   - When: Bot calculates P&L
   - Then: Should show -3.4 SOL loss, not 6.6 SOL profit

2. **As a developer**, I want to test follow-up context preservation so users get relevant responses
   - Given: User asks "why risky?" after FINNA trade
   - When: Bot processes the follow-up
   - Then: Response should reference FINNA, not OSCAR

3. **As a developer**, I want to verify tool selection so the bot uses accurate calculations
   - Given: A token with P&L data
   - When: Bot needs to calculate profit/loss
   - Then: Should use `calculate_token_pnl_from_trades`, not `fetch_token_pnl`

4. **As a developer**, I want to test position state consistency so users get accurate position info
   - Given: A partial sell of a token
   - When: Bot reports position state
   - Then: All systems should agree on remaining position

5. **As a developer**, I want to add new test scenarios easily so the test suite grows with issues
   - Given: A new bug found in production
   - When: I create a test scenario
   - Then: It should be simple to add and run

### Untested Critical Scenarios (Derived from User Feedback)

6. **As a trader**, I want the bot to recognize unusual position sizing and engage appropriately
   - Given: User takes 25% of bankroll position (vs typical 5-10%)
   - When: Bot processes the buy
   - Then: Should acknowledge the larger size and potentially ask about strategy
   - Example: "big position at 25% of bankroll. conviction play?"

7. **As a trader**, I want the bot to track partial sells intelligently
   - Given: User sells 30% of a position
   - When: Bot reports the sell
   - Then: Should note "took 30% off. still holding 70%" not just "sold BONK"
   - Why: User mentioned this is critical context for coaching

8. **As a trader**, I want follow-up questions to collect strategy context
   - Given: User buys at an unusual market cap for them
   - When: Bot notices pattern deviation
   - Then: Should ask ONE contextual question (not repetitive)
   - Example: "first time buying above $10M mcap. testing new range?"

9. **As a trader**, I want the bot to compare trades to my history
   - Given: User makes a trade
   - When: Bot has historical data
   - Then: Should note if unusual (size/timing/mcap) based on THEIR patterns
   - Not: Generic rules like "buying the top"

10. **As a trader**, I want goal mentions to be contextual not repetitive
    - Given: User is far from goal
    - When: Making small trades
    - Then: Don't mention goal every time
    - Only: When progress is significant or user asks

11. **As a trader**, I want the bot to remember multi-message context
    - Given: User says "thinking about buying POPCAT" then later "fuck it bought"
    - When: Bot sees the buy
    - Then: Should reference "you pulled the trigger on POPCAT"
    - Not: Treat as isolated event

12. **As a trader**, I want exit analysis relative to my entry
    - Given: User sells after multiple buys at different prices
    - When: Bot reports the exit
    - Then: Should show blended entry and exit efficiency
    - Example: "exited at 0.8x from $1.2M avg entry"

### High-level Task Breakdown

#### Task 1: Create Core Testing Infrastructure (2 hours)
- [x] Create `test_bot_scenarios.py` with ScenarioTester class
- [x] Implement test scenario data structure (trades, messages, expectations)
- [x] Build mock environment for diary/event store
- [x] Create test runner with clear pass/fail output
- **Verification**: Run a simple "hello world" test scenario successfully

#### Task 2: Create Test Scenarios from Real + Derived Cases (2 hours)
- [ ] Extract 5 real bug scenarios from logs (FINNA P&L, context loss, etc.)
- [ ] Create 7 untested scenarios based on user feedback:
  - Position sizing recognition (25% vs typical 5-10%)
  - Partial sell tracking (30% sold, 70% remaining)  
  - Strategy context collection (unusual mcap buy)
  - Historical pattern comparison (user's typical vs current)
  - Goal mention frequency (avoid repetition)
  - Multi-message context (thinking about → bought)
  - Exit efficiency analysis (blended entry calculation)
- [ ] Define test user profiles with typical patterns
- [ ] Create scenario JSON files with trades, messages, and expectations
- **Verification**: 12 total scenarios with clear pass/fail criteria

#### Task 3: Implement Test Harness with Real GPT (2 hours)
- [ ] Create TestDiaryAPI that provides scenario-specific data
- [ ] Set up real GPT client with production prompts
- [ ] Implement response caching for faster re-runs
- [ ] Add conversation flow manager for multi-turn tests
- [ ] Ensure actual trade processing logic is exercised
- **Verification**: Can run full conversation flows with real GPT

#### Task 4: Build Assertion Framework (1 hour)
- [ ] Implement two-tier output (summary + detailed drill-down)
- [ ] Add response content assertions (must_contain, must_not_contain)
- [ ] Add tool usage verification (which tools were called)
- [ ] Create P&L calculation validators
- [ ] Add position state consistency checks
- [ ] Build expandable conversation view for debugging
- **Verification**: Failed assertions show clear, actionable error messages

#### Task 5: Create Fast Feedback Loop (1 hour)
- [ ] Add response caching system for GPT calls
- [ ] Add --quick flag for running core 5 scenarios only
- [ ] Add --no-cache flag for testing prompt changes
- [ ] Create clear two-tier summary report
- [ ] Run each scenario 3x to check consistency
- **Verification**: Cached runs complete in <30 seconds

#### Task 6: Integration and Documentation (1 hour)
- [ ] Add pre-deployment checklist to run tests
- [ ] Create guide for adding new test scenarios
- [ ] Document common assertion patterns
- [ ] Add example of catching a real regression
- [ ] Create troubleshooting guide for test failures
- **Verification**: Can add a new test scenario in <5 minutes

### Key Challenges and Analysis

1. **Using Real GPT API**: Testing with actual API means slower tests but more accurate results
   - Solution: Cache GPT responses for repeated test runs
   - Use --no-cache flag when testing prompt changes

2. **GPT Non-Determinism**: GPT responses vary even with same input
   - Solution: Test for key elements present, not exact text matching
   - Run each scenario 3x and ensure consistency of core elements

3. **Output Clarity**: User needs both high-level summary and detailed drill-down
   - Solution: Two-tier output format:
     ```
     SUMMARY:
     ✅ FINNA P&L Calculation (3/3 assertions)
     ❌ Follow-up Context (1/3 assertions) 
     ✅ Position Sizing Alert (2/2 assertions)
     
     FAILED: Follow-up Context
     > Expected: Response mentions "FINNA"
     > Actual: "6.6 sol profit. bankroll up to 33.6 sol. nice exit at $2.1M mcap. keep grinding."
     > Context: User asked "why risky?" after FINNA trade
     > Full conversation: [click to expand]
     ```

4. **Historical Pattern Testing**: Testing "unusual for user" requires historical baseline
   - Solution: Create user profiles with typical patterns for testing
   - Example: TestUser1 usually trades 5-10% positions at $500K-$2M mcap

### Project Status Board

#### To Do
- [ ] Task 2: Create Test Scenarios from Real + Derived Cases
- [ ] Task 3: Implement Test Harness with Real GPT
- [ ] Task 4: Build Assertion Framework
- [ ] Task 5: Create Fast Feedback Loop
- [ ] Task 6: Integration and Documentation

#### In Progress
- [ ] Task 3: Implement Test Harness with Real GPT (Option A - Minimal)

#### Done
- [x] Task 1: Create Core Testing Infrastructure ✅
  - Created test_bot_scenarios.py with data structures
  - Implemented basic test runner with cache support
  - Two-tier output working (summary + details)
  - Framework runs successfully
- [x] Task 2: Create Test Scenarios from Real + Derived Cases ✅
  - Created 5 real bug scenarios (FINNA P&L, context loss, position state, tool selection, goal repetition)
  - Created 7 untested critical scenarios (position sizing, partial sells, strategy context, etc.)
  - All scenarios have clear assertions and expected behaviors
  - Scenarios load and run successfully in framework

### Executor's Feedback or Assistance Requests

**Task 1 Complete**: Core testing infrastructure is working! The framework runs successfully with color-coded output, caching, and clear assertions. Moving on to Task 2 to create the actual test scenarios based on real bugs and user feedback.

**Task 2 Complete**: All 12 test scenarios created successfully!
- 5 real bug scenarios: FINNA P&L duplication, context loss, position state conflicts, tool selection, goal repetition
- 7 untested critical behaviors: position sizing alerts, partial sell tracking, strategy context, user pattern recognition, etc.
- All scenarios have clear pass/fail criteria and are running in the framework

**Decision Point for Task 3**: To implement the test harness with real GPT, I need to integrate with the actual bot components. This requires:
1. Access to the real GPT client configuration (API keys, prompts)
2. Setting up a test database/diary API that won't interfere with production
3. Mocking the Telegram interface while using real GPT

Should I proceed with a minimal integration that focuses on testing the prompt/GPT responses, or do you want a fuller integration that includes the trade processing logic?

### Lessons
*To be documented during implementation*

### Success Criteria
- Can catch all 5 recent production bugs automatically
- Can test 7 additional critical behaviors not yet validated
- Full test suite (12 scenarios) runs in <2 minutes with cache
- First run with GPT calls completes in <5 minutes
- Two-tier output provides both summary and drill-down capability
- Adding new test scenarios takes <5 minutes
- Clear error messages that point to the exact issue
- No false positives that slow down development
- Catches regressions before they reach production

### Total Time Estimate
~8.5 hours of implementation work, which will save 20-30 minutes per deployment cycle going forward.

---

## 📋 Latest Updates (January 2025)

### ✅ Bot Testing Framework (Completed)
Implemented comprehensive testing framework to catch regressions:
- **Created**: `test_bot_scenarios.py` - Main test runner with caching
- **Created**: `test_scenarios/all_scenarios.py` - 12 test scenarios
- **Created**: `test_gpt_integration.py` - GPT client integration 
- **Created**: `test_results_report.html` - Visual test results
- **Created**: `TESTING_IMPROVEMENTS_SUMMARY.md` - Comprehensive docs

Key Features:
- Two-tier output (summary + detailed failures)
- Response caching for fast re-runs
- Real GPT integration testing
- Covers both past bugs and untested behaviors

### ✅ System Prompt Cleanup (Completed)
Cleaned up bloated coach prompt to remove unfounded claims:
- **Removed**: "usually dumps from here" and other baseless generalizations
- **Removed**: Untested time-based features ("3am trades hitting different")
- **Removed**: Entire "Enhanced Context Awareness" section (untested)
- **Simplified**: Reaction examples to just state facts, not interpretations
- **Reduced**: Analytics examples to essentials only

The bot now:
- States only what it can observe from data
- Doesn't make market behavior generalizations
- Keeps responses grounded in actual facts
- Maintains the dry, brief personality without fake expertise

### Current State
- Analytics system is live and working (phases 1-4 complete)
- Testing framework built and functional
- System prompt cleaned of unfounded assumptions
- Bot running with dual-write to events table
- Ready for handoff to continue development on another device