# 🚀 Trading Coach Deployment Guide

## Quick Start (5 minutes)

### Step 1: Check Your Setup
```bash
# You already have these:
✓ CIELO_KEY in .env
✓ Wallet address
✓ Trading history on Cielo
```

### Step 2: Choose Your Version
```python
# Option A: Basic version (start here)
from src.services.trading_coach import get_trade_coaching

# Option B: Enhanced version (more features)
from src.services.trading_coach_v2 import get_enhanced_trade_coaching
```

### Step 3: Add to Your Bot

#### Minimal Integration (Test First!)
```python
# Add this test command to verify it works
async def coach_test(update, context):
    """Test command: /coachtest"""
    
    # Test with your wallet
    result = await get_trade_coaching(
        wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        sol_amount=10.0,
        token_symbol="TEST"
    )
    
    if result['success']:
        message = f"{result['message']}\n\n{result['emoji']} {result['coaching']}"
    else:
        message = "❌ Coach unavailable"
    
    await update.message.reply_text(message, parse_mode='Markdown')
```

#### Full Buy Integration
```python
async def buy_with_coaching(update, context):
    """Enhanced /buy command with coaching"""
    
    # Parse command
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /buy <token> <sol_amount>")
        return
    
    token = context.args[0].upper()
    try:
        sol_amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount")
        return
    
    # Get user's wallet (adjust to your bot's logic)
    user_wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"  # TODO: Get from your DB
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    
    # Get coaching
    coaching = await get_trade_coaching(
        wallet=user_wallet,
        sol_amount=sol_amount,
        token_symbol=token
    )
    
    # Format message
    if coaching['success']:
        message = coaching['message']
        if 'statistics' in coaching:
            stats = coaching['statistics']
            # Add quick summary at top
            message = f"📊 {stats.get('total_patterns', 0)} similar trades found\n\n" + message
        
        message += f"\n\n{coaching['emoji']} {coaching['coaching']}"
        
        # Add buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Execute Trade", callback_data=f"exec_{token}_{sol_amount}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_trade")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        # Fallback if coaching fails
        await update.message.reply_text(
            f"⚠️ Coaching unavailable. Trade {token} with {sol_amount} SOL?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes", callback_data=f"exec_{token}_{sol_amount}"),
                InlineKeyboardButton("❌ No", callback_data="cancel_trade")
            ]])
        )

# Handle button clicks
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_trade":
        await query.edit_message_text("❌ Trade cancelled\n\n💡 Good traders know when NOT to trade!")
    
    elif query.data.startswith("exec_"):
        # Parse trade details
        parts = query.data.split("_")
        token = parts[1]
        amount = float(parts[2])
        
        await query.edit_message_text(f"🚀 Executing: Buy {token} with {amount} SOL...")
        
        # TODO: Add your actual trade execution here
```

### Step 4: Add Commands to Your Bot
```python
# In your main bot file
from telegram.ext import CommandHandler, CallbackQueryHandler

# Add handlers
dispatcher.add_handler(CommandHandler('coachtest', coach_test))
dispatcher.add_handler(CommandHandler('buy', buy_with_coaching))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
```

## Test Sequence

### 1. Basic Test
```
You: /coachtest
Bot: Shows patterns for 10 SOL trades
```

### 2. Real Trade Test
```
You: /buy BONK 5
Bot: Shows your historical 5 SOL patterns
```

### 3. Edge Cases
```
You: /buy BONK 0
Bot: Invalid amount

You: /buy BONK 1000
Bot: No historical data (new position size)
```

## What You'll See

### Success Case:
```
📊 5 similar trades found

**Last 5 times you bought with ~15.0 SOL:**

🟢 TOKEN1: 14.6 SOL → +39.6% (+23.1 SOL)
🔴 TOKEN2: 16.8 SOL → -15.1% (-12.7 SOL)
🟢 TOKEN3: 14.2 SOL → +13.2% (+11.2 SOL)

📊 **Stats**: 64% win rate, +12.5% avg ROI

🎯 Mixed results. What's your edge this time?

[✅ Execute Trade] [❌ Cancel]
```

### No Data Case:
```
📊 0 similar trades found

No historical data for ~1000.0 SOL trades.

🆕 This is a new position size for you. Start carefully and set clear stops.

[✅ Execute Trade] [❌ Cancel]
```

## Troubleshooting

### "Module not found"
```bash
cd /Users/satoshi/walletdoctor
export PYTHONPATH=$PWD:$PYTHONPATH
```

### "Cielo API error"
- Check CIELO_KEY is correct
- Try the curl test: `curl -H "x-api-key: YOUR_KEY" https://feed-api.cielo.finance/api/v1/test`

### "No patterns found"
- This is normal! It means no historical trades at that size
- The system still provides guidance

## Monitoring Success

Track these metrics:
1. **Usage**: How often is coaching viewed before trades?
2. **Behavior**: Do users cancel more trades after seeing patterns?
3. **Performance**: Do pattern-followers trade better?

## Next Steps

Once basic version works:
1. Switch to `trading_coach_v2.py` for enhanced features
2. Add wallet lookup from your database
3. Track which patterns lead to cancelled vs executed trades
4. Consider adding a "confidence" indicator

## Ready? 

1. Add the test command first
2. Try `/coachtest`
3. If it works, add the full buy integration
4. Ship it! 🚀

The moment of truth is here - let's see how your traders respond to seeing their patterns!