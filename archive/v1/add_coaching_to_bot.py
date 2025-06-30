#!/usr/bin/env python3
"""
Script to add coaching feature to the telegram bot
Run this to see the exact changes needed
"""

print("""
🎯 ADD COACHING TO YOUR BOT - Step by Step Guide

1. First, add this import at the top of telegram_bot_simple.py (around line 14):
   
   from src.services.trading_coach import get_trade_coaching
   
2. Add this method to the TradeBroBot class (anywhere after line 100):

    async def coach_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        '''Test the coaching system'''
        try:
            # Test with the wallet we've been using
            coaching = await get_trade_coaching(
                wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
                sol_amount=10.0,
                token_symbol="TEST"
            )
            
            if coaching['success']:
                message = coaching['message']
                message += f"\\n\\n{coaching['emoji']} {coaching['coaching']}"
                
                # Add stats if available
                if 'statistics' in coaching:
                    stats = coaching['statistics']
                    message += f"\\n\\n📊 Found {stats['total_patterns']} similar trades"
                    
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Coaching system unavailable")
                
        except Exception as e:
            logger.error(f"Coach test error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

3. Add this line in the run() method where handlers are added (line 710):
   
   application.add_handler(CommandHandler("coachtest", self.coach_test))

4. If you want to add coaching to the analyze command, modify the analyze_command method:

    # Add this after getting wallet stats (around line 365):
    
    # Show pattern coaching if they provide amount
    if len(context.args) > 1:
        try:
            sol_amount = float(context.args[1])
            coaching = await get_trade_coaching(
                wallet=wallet_address,
                sol_amount=sol_amount
            )
            
            if coaching['success'] and 'statistics' in coaching:
                stats = coaching['statistics']
                await update.message.reply_text(
                    f"📊 *Pattern Analysis for {sol_amount} SOL trades:*\\n"
                    f"Found {stats['total_patterns']} similar trades\\n"
                    f"Win rate: {stats['win_rate']:.0f}%\\n"
                    f"Avg ROI: {stats['avg_roi']:+.1f}%\\n\\n"
                    f"{coaching['emoji']} {coaching['coaching']}",
                    parse_mode='Markdown'
                )
        except ValueError:
            pass

5. Test it:
   - Start your bot
   - Type: /coachtest
   - You should see historical patterns!

ALTERNATIVE: Quick test without modifying the bot:

Create test_coaching_standalone.py:
""")

print('''
```python
import asyncio
from src.services.trading_coach import get_trade_coaching

async def test():
    result = await get_trade_coaching(
        wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        sol_amount=10.0
    )
    print(result)

asyncio.run(test())
```

Then run: python test_coaching_standalone.py
''')