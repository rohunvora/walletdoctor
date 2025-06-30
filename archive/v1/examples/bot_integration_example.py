#!/usr/bin/env python3
"""
Example of how to integrate the Trading Coach into the Telegram bot
This shows the actual implementation pattern for the bot handlers
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.trading_coach import get_trade_coaching
from dotenv import load_dotenv

load_dotenv()

# Example bot command handler
async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /buy command with pattern coaching
    Usage: /buy <token> <amount_sol>
    """
    
    # Parse command
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Usage: /buy <token> <amount_sol>\n"
                "Example: /buy BONK 10"
            )
            return
        
        token_symbol = args[0].upper()
        sol_amount = float(args[1])
        
        # Get user's wallet (would come from database in real bot)
        user_wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"  # Example
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        # Get coaching data
        coaching = await get_trade_coaching(
            wallet=user_wallet,
            sol_amount=sol_amount,
            token_symbol=token_symbol
        )
        
        if not coaching['success']:
            await update.message.reply_text(
                "⚠️ Unable to fetch trading patterns. Trade carefully!"
            )
            return
        
        # Build response message
        response = f"{coaching['message']}\n\n{coaching['emoji']} {coaching['coaching']}"
        
        # Create inline keyboard
        keyboard = []
        
        if coaching.get('show_trade_button', True):
            keyboard.append([
                InlineKeyboardButton(
                    "✅ Execute Trade", 
                    callback_data=f"execute_buy_{token_symbol}_{sol_amount}"
                ),
                InlineKeyboardButton(
                    "❌ Cancel", 
                    callback_data="cancel_trade"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                "📊 View Stats", 
                callback_data=f"view_stats_{user_wallet}"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send coaching message
        await update.message.reply_text(
            response,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number."
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {str(e)}"
        )

# Example callback handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("execute_buy_"):
        # Parse the trade details
        parts = data.split("_")
        token = parts[2]
        amount = float(parts[3])
        
        # Here you would execute the actual trade
        await query.edit_message_text(
            f"🚀 Executing buy order:\n"
            f"Token: {token}\n"
            f"Amount: {amount} SOL\n\n"
            f"⏳ Processing..."
        )
        
        # Simulate trade execution
        await asyncio.sleep(2)
        
        await query.edit_message_text(
            f"✅ Trade executed!\n"
            f"Bought {token} with {amount} SOL\n\n"
            f"📊 View in portfolio: /portfolio"
        )
        
    elif data == "cancel_trade":
        await query.edit_message_text(
            "❌ Trade cancelled.\n\n"
            "💡 Good traders know when NOT to trade!"
        )
        
    elif data.startswith("view_stats_"):
        wallet = data.split("_")[2]
        # Show wallet statistics
        await query.edit_message_text(
            "📊 Fetching your trading statistics..."
        )

# Example of quick buy with instant coaching
async def quick_buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Quick buy with automatic pattern detection
    Usage: /qb <amount_sol>
    """
    
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: /qb <amount_sol>\n"
                "Example: /qb 10"
            )
            return
        
        sol_amount = float(context.args[0])
        user_wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
        
        # Get patterns without specific token
        coaching = await get_trade_coaching(
            wallet=user_wallet,
            sol_amount=sol_amount
        )
        
        if coaching['success']:
            stats = coaching.get('statistics', {})
            
            # Quick summary
            summary = (
                f"🎯 **Quick Analysis for {sol_amount} SOL trades:**\n\n"
                f"Win Rate: {stats.get('win_rate', 0):.0f}%\n"
                f"Avg ROI: {stats.get('avg_roi', 0):+.1f}%\n"
                f"Total P&L: {stats.get('total_pnl_sol', 0):+.1f} SOL\n\n"
                f"{coaching['emoji']} {coaching['coaching']}"
            )
            
            await update.message.reply_text(
                summary,
                parse_mode="Markdown"
            )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid number"
        )

# Demo function to show the flow
async def demo_coaching_flow():
    """Demonstrate the coaching flow"""
    
    print("=== TELEGRAM BOT COACHING INTEGRATION ===\n")
    
    # Simulate user interactions
    scenarios = [
        ("User types:", "/buy NEWMEME 15"),
        ("User types:", "/qb 50"),
        ("User types:", "/buy PONKE 5")
    ]
    
    for user_input, command in scenarios:
        print(f"\n{user_input} {command}")
        print("-" * 50)
        
        # Parse command
        parts = command.split()
        if parts[0] == "/buy":
            token = parts[1]
            amount = float(parts[2])
            
            coaching = await get_trade_coaching(
                wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
                sol_amount=amount,
                token_symbol=token
            )
            
            print("Bot responds:")
            print(coaching['message'])
            print(f"\n{coaching['emoji']} {coaching['coaching']}")
            print("\n[✅ Execute Trade] [❌ Cancel] [📊 View Stats]")
            
        elif parts[0] == "/qb":
            amount = float(parts[1])
            
            coaching = await get_trade_coaching(
                wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
                sol_amount=amount
            )
            
            if coaching['success'] and 'statistics' in coaching:
                stats = coaching['statistics']
                print("Bot responds:")
                print(f"🎯 Quick Analysis for {amount} SOL trades:")
                print(f"Win Rate: {stats['win_rate']:.0f}%")
                print(f"Avg ROI: {stats['avg_roi']:+.1f}%")
                print(f"\n{coaching['emoji']} {coaching['coaching']}")

if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo_coaching_flow())
    
    print("\n\n=== INTEGRATION NOTES ===")
    print("1. Add these handlers to your bot:")
    print("   - dispatcher.add_handler(CommandHandler('buy', buy_command))")
    print("   - dispatcher.add_handler(CommandHandler('qb', quick_buy_command))")
    print("   - dispatcher.add_handler(CallbackQueryHandler(button_callback))")
    print("\n2. Set CIELO_KEY in your .env file")
    print("\n3. The coach will automatically cache data for 5 minutes")
    print("\n4. Users get instant feedback before every trade!")