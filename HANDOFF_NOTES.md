# Handoff Notes - Lean Pipeline Implementation

## Current State (as of deployment)

### ✅ What's Working
1. **Lean Pipeline Architecture** - Successfully replaced 6+ service architecture with simple flow:
   ```
   Wallet → Listener → Diary → Prompt Builder → GPT (with tools) → Telegram
   ```

2. **Performance** - Achieved <5ms requirement (4.6ms cold start)

3. **Bot Running** - @mytradebro_bot is live with all fixes applied

### 🐛 Recent Fixes Applied
1. **Bankroll Tracking** - Now uses actual RPC calls after trades (not math inference)
2. **Wallet Context** - Added wallet_address to prompt data for tool execution
3. **Response Length** - Reduced max_tokens from 150 → 80 for brevity
4. **Token Balance** - Fixed null handling in fetch_token_balance

### 📊 Test Results
- All infrastructure tests passing
- GPT tools working correctly
- Exact trade percentages preserved
- Cache performance: 1107x faster on hits

## 🎯 Next Focus: System Prompt Optimization

The technical infrastructure is solid. The main leverage point is now `coach_prompt_v1.md`.

### Known Issues with Current Prompt
1. **Too aggressive for casual messages** - "hey" gets analytical trade response
2. **No guidance for conversation flow** - Doesn't handle greetings appropriately
3. **Missing context awareness** - Same intensity for all message types

### OpenAI Testing Setup
To test prompts before deploying:

1. **Model**: gpt-4o-mini (not gpt-4.1)
2. **Max tokens**: 80
3. **Temperature**: 0.7
4. **System Prompt**: Copy from `coach_prompt_v1.md`
5. **Tools**: Add all 4 function definitions (see README)

### Test Context Examples
Use the realistic contexts in this repo:
- Fresh buy trades
- Partial sells
- Casual messages
- Loss scenarios
- Late night trades

## 🔧 Technical Details

### Database
- Single `pocket_coach.db` with diary table
- All events stored as JSON with exact values
- No rounding of percentages

### Active Components
- `telegram_bot_coach.py` - Main bot
- `diary_api.py` - Data access (with caching)
- `prompt_builder.py` - Minimal context builder
- `gpt_client.py` - GPT with tools
- `coach_prompt_v1.md` - System prompt (main optimization target)

### Archived (Not Used)
- conversation_engine.py
- enhanced_context_builder.py
- pattern_service.py
- state_manager.py
- nudge_engine.py

## 🚀 Deployment
Bot is running on original machine. To deploy elsewhere:
```bash
python3 telegram_bot_coach.py
```

Check PID file: `telegram_bot_coach.pid`

## 📝 Key Decisions Made
1. **Simplicity wins** - Removed all abstraction layers
2. **Trust the LLM** - GPT with tools > hardcoded patterns
3. **Exact data** - No rounding, preserve precision
4. **Performance first** - Sub-5ms is non-negotiable

---

Ready for prompt engineering phase. Infrastructure is solid. 