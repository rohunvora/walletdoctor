# Repository Cleanup Summary
*Date: December 2024*

## 🎯 Purpose
Cleaned up the repository to establish a clear ground truth before implementing the goal-oriented adaptive coach system.

## 📁 Files Archived

### To `docs/archive/`:
- `CONTEXT_AWARE_AI_PLAN.md` - Outdated pattern-based AI plan
- `REPOSITORY_CLEANUP_PLAN.md` - Old cleanup plan for two-bot system

### To `archive/misc_files/`:
- `coach_prompt_v1_updated.md` - Duplicate/confusing prompt file
- `conversation_manager.py` - Part of old abstraction layer
- `scratchpad.md` - Duplicate of .cursor/scratchpad.md
- `all_fixes_summary.md` - Historical fixes
- `follow_up_conversations_day1_summary.md` - Historical summary
- `pnl_validator.py` - Test file
- `test_market_cap_mock.py` - Test file
- `coachL_test_pack.json5` - Test data
- `MARKET_CAP_TESTING.md` - Test documentation
- `functions.md` - Misc notes
- `TEST_CONTEXTS.md` - Test contexts
- `PROJECT_STRUCTURE.md` - Outdated structure doc
- `PROJECT_CURRENT_STATE.md` - Outdated state doc

## ✅ Key Updates

### `.cursor/scratchpad.md`:
- Completely rewritten to focus on goal-oriented system
- Removed duplicate sections
- Clear implementation phases
- Deterministic formulas
- Core integration test

### `README.md`:
- Updated to reflect goal-oriented vision
- Natural conversation examples
- Clear goal system explanation
- Removed outdated features
- Added coming soon sections

## 📂 Current Structure

### Active Files (Goal-Oriented Coach):
- `telegram_bot_coach.py` - Main bot
- `diary_api.py` - Data layer
- `prompt_builder.py` - Context builder
- `gpt_client.py` - GPT with tools
- `coach_prompt_v1.md` - System prompt
- `price_history_service.py` - Price monitoring
- `metrics_collector.py` - Metrics tracking

### Separate Product:
- `telegram_bot_simple.py` - Tradebro analyzer bot (kept separate)

### Documentation:
- `.cursor/scratchpad.md` - Clean implementation plan
- `README.md` - Updated for goal-oriented system
- `BOT_MANAGEMENT.md` - Deployment guide
- `TESTING_GUIDE.md` - Testing procedures

## 🎯 Next Steps

Ready to implement Phase 1+2 of the goal-oriented system:
1. Create goal/facts database tables
2. Build onboarding flow with 3-cycle limit
3. Implement goal parsing with confirmation
4. Add deterministic goal calculators
5. Create GPT tools for goal/fact management
6. Write core integration test 