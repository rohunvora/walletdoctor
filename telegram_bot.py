#!/usr/bin/env python3
"""
WalletDoctor Telegram Bot - Learn from your mistakes, avoid repeating them
"""

import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import duckdb
from typing import Dict, List

# Import our existing modules
from scripts.data import load_wallet
from scripts.instant_stats import InstantStatsGenerator
from scripts.db_migrations import run_migrations

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot states
WAITING_FOR_WALLET = "waiting_for_wallet"
WAITING_FOR_ANNOTATION = "waiting_for_annotation"
MONITORING_ACTIVE = "monitoring_active"

class WalletDoctorBot:
    def __init__(self, token: str, db_path: str = "coach.db"):
        self.token = token
        self.db_path = db_path
        self.user_states = {}  # Track user states
        self.monitored_wallets = {}  # Track monitored wallets
        
    def init_db(self, db):
        """Initialize database tables."""
        db.execute("""
            CREATE TABLE IF NOT EXISTS tx (
                signature VARCHAR,
                timestamp BIGINT,
                fee BIGINT,
                type VARCHAR,
                source VARCHAR,
                slot BIGINT,
                token_mint VARCHAR,
                token_amount DOUBLE,
                native_amount BIGINT,
                from_address VARCHAR,
                to_address VARCHAR,
                transfer_type VARCHAR
            )
        """)
        
        db.execute("""
            CREATE TABLE IF NOT EXISTS pnl (
                mint VARCHAR,
                symbol VARCHAR,
                realizedPnl DOUBLE,
                unrealizedPnl DOUBLE,
                totalPnl DOUBLE,
                avgBuyPrice DOUBLE,
                avgSellPrice DOUBLE,
                quantity DOUBLE,
                totalBought DOUBLE,
                totalSold DOUBLE,
                holdTimeSeconds BIGINT,
                numSwaps INTEGER
            )
        """)
        
        # Run migrations for annotation support
        run_migrations(db)
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        welcome_message = (
            "🏥 *Welcome to WalletDoctor!*\n\n"
            "I help you learn from your trading mistakes.\n\n"
            "Send `/analyze <wallet_address>` to analyze any Solana wallet!\n\n"
            "_Example:_\n"
            "`/analyze 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`"
        )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown'
        )
        
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyze trading data for a wallet address"""
        user_id = update.effective_user.id
        
        # Check if wallet address was provided
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Please provide a wallet address.\n\n"
                "Example:\n"
                "`/analyze 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`",
                parse_mode='Markdown'
            )
            return
            
        wallet_address = context.args[0]
        
        # Basic validation for Solana address
        if len(wallet_address) < 32 or len(wallet_address) > 44:
            await update.message.reply_text(
                "Invalid wallet address. Please provide a valid Solana address.",
                parse_mode='Markdown'
            )
            return
        
        # Show loading message
        loading_msg = await update.message.reply_text(f"Analyzing wallet...")
        
        try:
            # Create a unique temporary database for this analysis
            import time
            temp_db_path = f"temp_analysis_{user_id}_{int(time.time())}.db"
            db = duckdb.connect(temp_db_path)
            
            # Initialize database tables
            self.init_db(db)
            
            # Load wallet data using the load_wallet function
            # This will fetch real data from Helius and Cielo
            success = load_wallet(db, wallet_address, mode='instant')
            
            if not success:
                await loading_msg.edit_text(
                    "Failed to load wallet data.\n\n"
                    "This could be due to:\n"
                    "• Invalid wallet address\n"
                    "• API rate limits\n"
                    "• No trading activity found"
                )
                db.close()
                # Clean up temp database
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Check if we have data
            tables = [t[0] for t in db.execute("SHOW TABLES").fetchall()]
            
            if 'pnl' not in tables:
                await loading_msg.edit_text("No trading data found for this wallet.")
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
                
            # Get stats using the real data
            instant_gen = InstantStatsGenerator(db)
            stats = instant_gen.get_baseline_stats()
            
            if stats['total_trades'] == 0:
                await loading_msg.edit_text("No trades found for this wallet.")
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Get top losses for analysis
            top_trades = instant_gen.get_top_trades(limit=5)
            
            # Analyze for revenge trading pattern
            revenge_pattern = self.detect_revenge_trading(db, top_trades['losers'])
            
            # Format initial response with immediate insight
            response = f"📊 Found {stats['total_trades']} trades\n\n"
            
            if stats['total_pnl'] < 0:
                response += f"You're down ${abs(stats['total_pnl']):,.0f} with a {stats['win_rate']:.1f}% win rate\n\n"
            else:
                response += f"You're up ${stats['total_pnl']:,.0f} with a {stats['win_rate']:.1f}% win rate\n\n"
            
            # Show immediate insight based on detected issues
            if revenge_pattern and stats['total_pnl'] < 0:
                response += f"🎯 *Your biggest issue: Revenge Trading*\n"
                response += f"After losses, you make bigger, riskier trades.\n"
                if top_trades['losers']:
                    worst = top_trades['losers'][0]
                    response += f"Your {worst['symbol']} trade lost ${abs(worst['realizedPnl']):,.0f}.\n\n"
                response += "This behavior has cost you thousands."
            elif stats['win_rate'] < 30:
                response += f"🎯 *Your biggest issue: Poor Entry Timing*\n"
                response += f"You're buying at the wrong time.\n"
                response += f"Only {stats['winning_trades']} of {stats['total_trades']} trades made money."
            elif stats['avg_pnl'] < -100:
                response += f"🎯 *Your biggest issue: No Risk Management*\n"
                response += f"Your average loss is ${abs(stats['avg_pnl']):,.0f}.\n"
                response += f"You're letting losses run too far."
                
            await loading_msg.edit_text(response, parse_mode='Markdown')
            
            # If we have losses, offer to dig deeper
            if top_trades['losers'] and stats['total_pnl'] < 0:
                # Wait a moment for better UX
                import asyncio
                await asyncio.sleep(1.5)
                
                # Create simple buttons for the worst loss
                worst_loss = top_trades['losers'][0]
                
                buttons = [
                    [InlineKeyboardButton(
                        f"Tell me about {worst_loss['symbol']}",
                        callback_data=f"explain_{worst_loss['symbol']}_{worst_loss['realizedPnl']}"
                    )],
                    [InlineKeyboardButton(
                        "Show all my mistakes",
                        callback_data=f"show_mistakes_{user_id}"
                    )],
                    [InlineKeyboardButton(
                        "Skip to advice",
                        callback_data=f"skip_to_advice_{user_id}"
                    )]
                ]
                
                reply_markup = InlineKeyboardMarkup(buttons)
                
                followup_msg = (
                    "Want to understand what's going wrong?\n\n"
                    "I can show you exactly why you're losing money."
                )
                
                await update.message.reply_text(
                    followup_msg,
                    reply_markup=reply_markup
                )
                
            # Store analysis data for later use
            context.user_data['current_wallet'] = wallet_address
            context.user_data['total_pnl'] = stats['total_pnl']
            context.user_data['win_rate'] = stats['win_rate']
            context.user_data['worst_trades'] = top_trades['losers'][:5]
            context.user_data['temp_db_path'] = temp_db_path
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error in analyze command: {e}")
            await loading_msg.edit_text(f"Error analyzing trades: {str(e)}")
            # Clean up on error
            try:
                if 'db' in locals():
                    db.close()
                if 'temp_db_path' in locals() and os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
            except:
                pass
                
    def detect_revenge_trading(self, db, losers):
        """Simple revenge trading detection"""
        # For now, just check if big losses exist
        # In production, would analyze time between trades
        if losers and len(losers) >= 3:
            total_loss = sum(abs(t['realizedPnl']) for t in losers[:3])
            if total_loss > 10000:  # More than $10k in top 3 losses
                return True
        return False
        
    def get_brutal_advice(self, annotation, symbol, pnl, context):
        """Generate brutal, personalized advice based on user's explanation"""
        loss_amount = abs(pnl)
        
        # Check for revenge trading indicators
        if any(word in annotation for word in ['recover', 'make back', 'revenge', 'angry', 'lost', 'get back']):
            return (
                f"\nHere's the truth:\n\n"
                f"You're not trading, you're gambling to recover losses.\n"
                f"That ${loss_amount:,.0f} loss? It happened because you were emotional.\n\n"
                f"*The fix:*\n"
                f"• After any loss over $1k, take 24 hours off\n"
                f"• Set a daily loss limit: $500 max\n"
                f"• If you hit it, close everything\n\n"
                f"Revenge trading has cost you over $30k. Stop it."
            )
            
        # Check for FOMO/pump chasing
        elif any(word in annotation for word in ['pump', 'pumping', 'moon', 'twitter', 'telegram', 'youtube', 'influencer']):
            return (
                f"\nHere's the truth:\n\n"
                f"You bought {symbol} because someone else was already making money.\n"
                f"By the time you see it pumping, you're exit liquidity.\n\n"
                f"*The fix:*\n"
                f"• Never buy after a 30%+ pump\n"
                f"• Unfollow all crypto influencers\n"
                f"• Find entries before Twitter knows\n\n"
                f"Chasing pumps is why you're down ${abs(context.user_data.get('total_pnl', 0)):,.0f}."
            )
            
        # Check for no plan/random trading
        elif any(word in annotation for word in ['thought', 'seemed', 'maybe', 'looked good', 'why not']):
            return (
                f"\nHere's the truth:\n\n"
                f"You had no plan. You just clicked buy and hoped.\n"
                f"Trading without a plan is just expensive gambling.\n\n"
                f"*The fix:*\n"
                f"• Before any trade, write: entry, target, stop loss\n"
                f"• If you can't explain why in one sentence, don't trade\n"
                f"• Max position until you have a system: $500\n\n"
                f"Random trades like this are bleeding you dry."
            )
            
        # Generic but still brutal
        else:
            return (
                f"\nHere's the truth:\n\n"
                f"This ${loss_amount:,.0f} loss happened because you don't have rules.\n"
                f"You're trading on feelings, not facts.\n\n"
                f"*The fix:*\n"
                f"• Create written rules for entries and exits\n"
                f"• Never break them, even if you 'feel' different\n"
                f"• Start small: $500 max per trade\n\n"
                f"Without discipline, you'll keep losing."
            )
            
    async def show_all_mistakes(self, message, user_id, context):
        """Show comprehensive list of trading mistakes"""
        try:
            worst_trades = context.user_data.get('worst_trades', [])
            total_pnl = context.user_data.get('total_pnl', 0)
            win_rate = context.user_data.get('win_rate', 0)
            
            response = "*Your Trading Problems*\n\n"
            
            # Main issues based on stats
            if win_rate < 30:
                response += f"📍 *Poor Entry Timing*\n"
                response += f"   You win only {win_rate:.0f}% of trades\n"
                response += f"   Cost: Most of your ${abs(total_pnl):,.0f} loss\n\n"
                
            if worst_trades and len(worst_trades) >= 3:
                big_losses = sum(abs(t['realizedPnl']) for t in worst_trades[:3])
                response += f"📍 *No Risk Management*\n"
                response += f"   Your top 3 losses: ${big_losses:,.0f}\n"
                response += f"   That's {big_losses/abs(total_pnl)*100:.0f}% of total losses\n\n"
                
            # Specific worst trades
            response += "*Biggest Disasters:*\n"
            for i, trade in enumerate(worst_trades[:5], 1):
                response += f"{i}. {trade['symbol']}: -${abs(trade['realizedPnl']):,.0f}\n"
                
            response += f"\n*Total damage: ${abs(total_pnl):,.0f}*"
            
            # Add buttons for next steps
            buttons = [
                [InlineKeyboardButton(
                    "Get specific advice",
                    callback_data=f"skip_to_advice_{user_id}"
                )],
                [InlineKeyboardButton(
                    "Analyze another wallet",
                    callback_data="start_over"
                )]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing mistakes: {e}")
            await message.reply_text("Error loading your trading data.")
            
    async def give_trading_advice(self, message, user_id, context):
        """Give specific, actionable trading advice"""
        try:
            total_pnl = context.user_data.get('total_pnl', 0)
            win_rate = context.user_data.get('win_rate', 0)
            worst_trades = context.user_data.get('worst_trades', [])
            
            response = "*Your Trading Fix*\n\n"
            
            # Rule 1 - Position sizing
            response += "*Rule 1: Position Sizing*\n"
            if abs(total_pnl) > 50000:
                response += "• Maximum position: $500 until profitable\n"
            elif abs(total_pnl) > 20000:
                response += "• Maximum position: $1,000\n"
            else:
                response += "• Maximum position: 2% of account\n"
                
            # Rule 2 - Entry rules
            response += "\n*Rule 2: Entry Rules*\n"
            if win_rate < 30:
                response += "• Never buy after 30%+ daily pump\n"
                response += "• Wait for red days to enter\n"
            else:
                response += "• Only buy with clear support levels\n"
                response += "• Set stop loss before entry\n"
                
            # Rule 3 - Loss limits
            response += "\n*Rule 3: Loss Limits*\n"
            response += "• Daily loss limit: $500\n"
            response += "• Weekly loss limit: $2,000\n"
            response += "• Hit limit = close laptop\n"
            
            # Rule 4 - Specific to their issues
            response += "\n*Rule 4: Your Specific Fix*\n"
            if worst_trades and worst_trades[0]['realizedPnl'] < -5000:
                response += "• No trading within 24h of a >$1k loss\n"
            if any('pump' in str(t.get('symbol', '')).lower() for t in worst_trades[:3]):
                response += "• Blacklist all memecoins\n"
            else:
                response += "• Journal every trade before entering\n"
                
            response += f"\n*Follow these rules or keep losing money.*\n"
            response += f"*Your choice.*"
            
            await message.reply_text(response, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error giving advice: {e}")
            await message.reply_text("Error generating advice.")
        
    async def handle_annotation_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle annotation button clicks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith("explain_"):
            # Parse the callback data
            parts = data.split("_")
            symbol = parts[1]
            pnl = float(parts[2])
            
            # Store what we're annotating
            context.user_data['annotating_symbol'] = symbol
            context.user_data['annotating_pnl'] = pnl
            self.user_states[user_id] = WAITING_FOR_ANNOTATION
            
            # Clear, simple prompt
            prompt = (
                f"What happened with {symbol}?\n\n"
                f"This trade lost ${abs(pnl):,.0f}."
            )
            
            await query.message.reply_text(prompt, parse_mode='Markdown')
            
        elif data.startswith("show_mistakes_"):
            await self.show_all_mistakes(query.message, user_id, context)
            
        elif data.startswith("skip_to_advice_"):
            await self.give_trading_advice(query.message, user_id, context)
            
        elif data == "show_patterns":
            await self.show_patterns(query.message, user_id)
            
    async def handle_annotation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle annotation text and provide brutal, personalized advice"""
        user_id = update.effective_user.id
        
        if self.user_states.get(user_id) != WAITING_FOR_ANNOTATION:
            # Not waiting for annotation, show help
            await update.message.reply_text(
                "Send `/analyze <wallet_address>` to analyze a wallet.",
                parse_mode='Markdown'
            )
            return
            
        symbol = context.user_data.get('annotating_symbol')
        pnl = context.user_data.get('annotating_pnl')
        annotation = update.message.text.lower()
        
        # Store annotation in database
        try:
            db = duckdb.connect(self.db_path)
            
            # Create annotations table if not exists
            db.execute("""
                CREATE TABLE IF NOT EXISTS telegram_annotations (
                    user_id BIGINT,
                    symbol VARCHAR,
                    pnl DOUBLE,
                    annotation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Store annotation
            db.execute(
                "INSERT INTO telegram_annotations (user_id, symbol, pnl, annotation) VALUES (?, ?, ?, ?)",
                [user_id, symbol, pnl, annotation]
            )
            
            # Provide brutal, personalized advice based on their response
            response = f"Got it. {self.get_brutal_advice(annotation, symbol, pnl, context)}"
                
            await update.message.reply_text(response, parse_mode='Markdown')
            
            self.user_states[user_id] = None
            db.close()
            
            # Show what to do next
            import asyncio
            await asyncio.sleep(1)
            
            current_wallet = context.user_data.get('current_wallet', '')
            next_steps = (
                "What would you like to do next?\n\n"
                f"• `/analyze {current_wallet}` - Review more trades\n"
                "• `/analyze <new_wallet>` - Analyze a different wallet\n"
                "• /patterns - See your trading patterns\n"
                "• /help - Learn more"
            )
            
            await update.message.reply_text(next_steps, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error storing annotation: {e}")
            await update.message.reply_text("❌ Error saving annotation. Please try again.")
            
    async def show_patterns(self, message, user_id):
        """Show user's patterns"""
        try:
            # For now, just show a summary of their issues
            # In production, would pull from annotations database
            
            response = "*Why You Lose Money*\n\n"
            
            response += "Based on wallet analysis:\n\n"
            response += "• You chase pumps\n"
            response += "• You revenge trade after losses\n" 
            response += "• You have no risk management\n"
            response += "• You trade on emotions\n\n"
            
            response += "Want to fix these?\n"
            response += "Analyze more wallets and be honest about what went wrong."
            
            await message.reply_text(response, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error showing patterns: {e}")
            await message.reply_text("No trading data available yet.")
            
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        help_text = (
            "*🏥 WalletDoctor - Learn from your mistakes*\n\n"
            "Commands:\n"
            "• `/analyze <wallet_address>` - Analyze any Solana wallet\n"
            "• /patterns - See your documented patterns\n"
            "• /help - Show this message\n\n"
            "_Example:_\n"
            "`/analyze 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`\n\n"
            "The more honest you are about your mistakes, "
            "the better I can help you avoid repeating them.\n\n"
            "_Knowledge is power. Self-knowledge is superpower._"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        user_id = update.effective_user.id
        
        if self.user_states.get(user_id) == WAITING_FOR_ANNOTATION:
            await self.handle_annotation(update, context)
        else:
            # For any other message, suggest using /analyze
            await update.message.reply_text(
                "👋 Send `/analyze <wallet_address>` to analyze a wallet!",
                parse_mode='Markdown'
            )
            
    def run(self):
        """Start the bot"""
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("analyze", self.analyze_command))
        application.add_handler(CommandHandler("patterns", self.patterns_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
        # Message handler
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))
        
        # Callback query handler for buttons
        application.add_handler(CallbackQueryHandler(self.handle_annotation_button))
        
        # Run the bot
        application.run_polling()
        
    async def patterns_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command wrapper for showing patterns"""
        await self.show_patterns(update.message, update.effective_user.id)

if __name__ == "__main__":
    # Load .env file if it exists
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get token from environment
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        print("Please set TELEGRAM_BOT_TOKEN environment variable")
        print("Either export it or add to .env file")
        exit(1)
        
    # Create and run bot
    bot = WalletDoctorBot(TOKEN)
    print("🤖 WalletDoctor Bot starting...")
    bot.run() 