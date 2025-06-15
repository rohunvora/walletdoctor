#!/usr/bin/env python3
"""
Tradebro Telegram Bot - Learn from your mistakes, avoid repeating them
"""

import os
import logging
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import duckdb
from typing import Dict, List
import asyncio

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

class TradeBroBot:
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
            "🏥 *Welcome to Tradebro!*\n\n"
            "I help you learn from your trading mistakes.\n\n"
            "Send `/analyze <wallet_address>` to analyze any Solana wallet!\n\n"
            "_Example:_\n"
            "`/analyze rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK`"
        )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown'
        )
        
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyze wallet for trading patterns - ONE perfect insight"""
        if not update.message or not context.args:
            await update.message.reply_text("Please provide a wallet address: `/analyze <address>`", parse_mode='Markdown')
            return
            
        wallet_address = context.args[0]
        user_id = update.effective_user.id
        
        # Validate Solana address
        try:
            if len(wallet_address) < 32 or len(wallet_address) > 44:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid Solana wallet address")
            return
            
        # Create a unique temporary database for this analysis
        temp_db_path = f"/tmp/tradebro_{user_id}_{int(time.time())}.db"
        
        # Send loading message
        loading_msg = await update.message.reply_text("🔍 Analyzing...")
        
        try:
            # Connect to temp database
            db = duckdb.connect(temp_db_path)
            self.init_db(db)
            
            # Load wallet data
            success = load_wallet(db, wallet_address, mode='instant')
            
            if not success:
                await loading_msg.edit_text(
                    "📊 *No trading data found*\n\n"
                    "This wallet either:\n"
                    "• Has never traded on Solana DEXs\n"
                    "• Is too new (data not indexed yet)\n"
                    "• Only holds tokens (no trades)",
                    parse_mode='Markdown'
                )
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Check if we have data
            tables = [t[0] for t in db.execute("SHOW TABLES").fetchall()]
            
            if 'pnl' not in tables:
                await loading_msg.edit_text(
                    "📊 *No trading data found*\n\n"
                    "Try a wallet that has traded on Raydium, Orca, or Jupiter.",
                    parse_mode='Markdown'
                )
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Get the most recent significant loss (or interesting trade)
            # First, let's check if we have transaction data for timing
            has_tx_data = 'tx' in tables
            
            # Get recent losses sorted by recency and impact
            recent_losses_query = """
                SELECT 
                    symbol,
                    totalPnl as pnl,
                    avgBuyPrice,
                    avgSellPrice,
                    totalBought,
                    totalSold,
                    numSwaps
                FROM pnl
                WHERE totalPnl < -1000  -- At least $1k loss
                ORDER BY 
                    CASE 
                        WHEN avgSellPrice > 0 THEN avgSellPrice / avgBuyPrice
                        ELSE avgBuyPrice
                    END DESC,
                    ABS(totalPnl) DESC
                LIMIT 10
            """
            
            losses = db.execute(recent_losses_query).fetchall()
            
            if not losses:
                # No significant losses? Check if they're profitable
                total_pnl = db.execute("SELECT SUM(totalPnl) FROM pnl").fetchone()[0]
                
                if total_pnl > 0:
                    # Profitable trader - find their worst performer
                    worst_trade = db.execute("""
                        SELECT symbol, totalPnl, avgBuyPrice, avgSellPrice, numSwaps
                        FROM pnl
                        WHERE totalPnl < 0
                        ORDER BY totalPnl ASC
                        LIMIT 1
                    """).fetchone()
                    
                    if worst_trade:
                        symbol, pnl, buy_price, sell_price, swaps = worst_trade
                        
                        response = f"You're up ${total_pnl:,.0f} overall.\n\n"
                        response += f"But {symbol} still cost you ${abs(pnl):,.0f}.\n\n"
                        
                        if sell_price > 0 and buy_price > 0:
                            loss_pct = ((sell_price - buy_price) / buy_price) * 100
                            response += f"You bought, watched it drop {abs(loss_pct):.0f}%, and held.\n\n"
                        
                        response += f"Even winners have blind spots."
                    else:
                        response = f"You're up ${total_pnl:,.0f} with zero losses.\n\n"
                        response += "Genuinely impressive.\n\n"
                        response += "But are you taking enough risk?"
                else:
                    # Losing trader but no single big loss
                    response = f"Down ${abs(total_pnl):,.0f} from death by a thousand cuts.\n\n"
                    response += "No huge disasters. Just consistent bad timing.\n\n"
                    response += "Sometimes that's worse."
                
                await loading_msg.edit_text(response)
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Analyze the most impactful recent loss
            symbol, pnl, buy_price, sell_price, bought, sold, swaps = losses[0]
            
            # Calculate what happened
            if sell_price > 0 and buy_price > 0:
                # They sold at a loss
                drop_pct = ((sell_price - buy_price) / buy_price) * 100
                
                # Look for pump chasing pattern
                # If buy price is much higher than sell, they bought high
                if buy_price > sell_price * 1.5:  # Bought 50%+ higher than sold
                    response = f"3 days ago you lost ${abs(pnl):,.0f} on {symbol}.\n\n"
                    response += f"You bought after it pumped, then held while it dropped {abs(drop_pct):.0f}%.\n\n"
                    response += "This isn't your only revenge trade."
                    
                elif swaps > 10:  # Overtrading
                    response = f"You lost ${abs(pnl):,.0f} on {symbol}.\n\n"
                    response += f"{swaps} trades on one token. Each one making it worse.\n\n"
                    response += "Overtrading is revenge trading in disguise."
                    
                else:  # Generic bad timing
                    response = f"Your {symbol} trade: -${abs(pnl):,.0f}\n\n"
                    response += f"Bought at ${buy_price:.4f}, sold at ${sell_price:.4f}.\n"
                    response += f"A {abs(drop_pct):.0f}% loss.\n\n"
                    response += "Your timing needs work."
            else:
                # They're still holding (no sell price)
                response = f"You're down ${abs(pnl):,.0f} on {symbol}.\n\n"
                response += f"Still holding. Still hoping.\n\n"
                response += "Hope isn't a strategy."
            
            # Send the focused insight
            await loading_msg.edit_text(response)
            
            # Store minimal data for potential future use
            context.user_data['last_analysis'] = {
                'wallet': wallet_address,
                'timestamp': datetime.now(),
                'loss_symbol': symbol,
                'loss_amount': abs(pnl)
            }
            
            db.close()
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
                
        except Exception as e:
            logger.error(f"Error in analyze command: {e}")
            await loading_msg.edit_text(f"Error analyzing wallet: {str(e)}")
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
        
        # More sophisticated analysis using actual content
        annotation_lower = annotation.lower()
        worst_trades = context.user_data.get('worst_trades', [])
        total_pnl = context.user_data.get('total_pnl', 0)
        
        # Check for social media driven trades
        if any(word in annotation_lower for word in ['twitter', 'telegram', 'discord', 'youtube', 'tiktok', 'reddit', 'friend', 'group', 'heard']):
            source = next((word for word in ['twitter', 'telegram', 'discord', 'youtube', 'tiktok', 'reddit'] if word in annotation_lower), 'social media')
            return (
                f"I see what happened.\n\n"
                f"You bought {symbol} because {source} told you to.\n"
                f"You're not trading - you're following strangers who dump on you.\n\n"
                f"Look at your results:\n"
                f"• This trade: -${loss_amount:,.0f}\n"
                f"• Total damage: -${abs(total_pnl):,.0f}\n"
                f"• Following others' calls has destroyed your account\n\n"
                f"*Fix this or go broke:*\n"
                f"• Delete {source}. Today.\n"
                f"• Never buy what others are shilling\n"
                f"• If you can't find your own trades, stop trading\n\n"
                f"Harsh? Your -${abs(total_pnl):,.0f} is harsher."
            )
            
        # Check for revenge trading with context
        elif any(word in annotation_lower for word in ['recover', 'make back', 'lost', 'down', 'red', 'loss', 'trying to get']):
            # Calculate how much revenge trading has cost them
            if worst_trades and len(worst_trades) >= 2:
                revenge_losses = sum(abs(t['realizedPnl']) for t in worst_trades[:3])
                return (
                    f"I knew it.\n\n"
                    f"You were trying to recover losses when you bought {symbol}.\n"
                    f"This isn't trading - it's gambling addiction.\n\n"
                    f"The numbers don't lie:\n"
                    f"• This revenge trade: -${loss_amount:,.0f}\n"
                    f"• Your top 3 disasters: -${revenge_losses:,.0f}\n"
                    f"• That's {revenge_losses/abs(total_pnl)*100:.0f}% of all losses!\n\n"
                    f"*You have two choices:*\n"
                    f"1. Keep revenge trading until you're broke\n"
                    f"2. Follow these rules:\n"
                    f"   • After ANY loss: 24 hour timeout\n"
                    f"   • Daily loss limit: $500\n"
                    f"   • Hit the limit = close everything\n\n"
                    f"Your ego or your money. Choose."
                )
            
        # Check for FOMO/pump chasing
        elif any(word in annotation_lower for word in ['pump', 'pumping', 'moon', 'rising', 'going up', 'green', '100x', 'missed']):
            return (
                f"Classic FOMO.\n\n"
                f"You saw {symbol} pumping and couldn't resist.\n"
                f"You know what you were? Exit liquidity.\n\n"
                f"This pattern is killing you:\n"
                f"• See green candles → FOMO buy → Red portfolio\n"
                f"• Your loss rate proves it: {100 - context.user_data.get('win_rate', 0):.0f}%\n"
                f"• You're literally buying other people's profits\n\n"
                f"*Want to stop being exit liquidity?*\n"
                f"• Never buy after 20%+ daily gains\n"
                f"• Only buy red. Only sell green.\n"
                f"• If you missed it, you missed it. Move on.\n\n"
                f"Stop chasing. Start thinking."
            )
            
        # Check for no plan/hope trading
        elif any(word in annotation_lower for word in ['thought', 'maybe', 'hoped', 'seemed', 'looked', 'felt', 'guess', 'why not']):
            return (
                f"No plan. No strategy. Just hope.\n\n"
                f"You bought {symbol} on a feeling.\n"
                f"Feelings cost you ${loss_amount:,.0f} this time.\n"
                f"Total feelings bill: ${abs(total_pnl):,.0f}\n\n"
                f"*Professional traders have:*\n"
                f"• Entry rules\n"
                f"• Exit rules\n"
                f"• Position sizing rules\n\n"
                f"*You have:*\n"
                f"• Feelings\n"
                f"• Hope\n"
                f"• -${abs(total_pnl):,.0f}\n\n"
                f"Get a system or get a job."
            )
            
        # Check for specific token patterns
        elif any(pattern in symbol.lower() for pattern in ['inu', 'elon', 'doge', 'shib', 'floki', 'moon', 'rocket']):
            return (
                f"Another memecoin. Of course.\n\n"
                f"{symbol} was never an investment.\n"
                f"It was a lottery ticket. You lost.\n\n"
                f"Your memecoin addiction:\n"
                f"• This loss: -${loss_amount:,.0f}\n"
                f"• Total account damage: -${abs(total_pnl):,.0f}\n"
                f"• Memecoins are why you're broke\n\n"
                f"*The only cure:*\n"
                f"• Blacklist ALL memecoins\n"
                f"• Trade only top 50 market cap\n"
                f"• If it has a dog logo, run\n\n"
                f"Stop gambling on garbage."
            )
            
        # More intelligent generic response based on their trading data
        else:
            # Calculate some key metrics
            avg_loss = sum(abs(t['realizedPnl']) for t in worst_trades[:5]) / min(len(worst_trades), 5) if worst_trades else loss_amount
            
            return (
                f"Let me be clear.\n\n"
                f"You lost ${loss_amount:,.0f} on {symbol} because you trade without rules.\n"
                f"No edge. No system. No discipline.\n\n"
                f"Your account tells the story:\n"
                f"• Average disaster: -${avg_loss:,.0f}\n"
                f"• Win rate: {context.user_data.get('win_rate', 0):.0f}%\n"
                f"• Total destruction: -${abs(total_pnl):,.0f}\n\n"
                f"*Three rules to save your account:*\n"
                f"1. Max position: $500 until profitable\n"
                f"2. Stop loss on EVERY trade: 5%\n"
                f"3. Journal before you buy, not after you lose\n\n"
                f"Follow rules or lose everything.\n"
                f"Your choice."
            )
            
    async def show_all_mistakes(self, message, user_id, context):
        """Show comprehensive breakdown of trading performance"""
        try:
            worst_trades = context.user_data.get('worst_trades', [])
            best_trades = context.user_data.get('best_trades', [])
            total_pnl = context.user_data.get('total_pnl', 0)
            win_rate = context.user_data.get('win_rate', 0)
            
            response = "*Your Trading Breakdown*\n\n"
            
            # Show strengths for profitable traders
            if total_pnl > 0:
                response += f"💰 *Net Result: +${total_pnl:,.0f}*\n"
                response += f"📊 Win Rate: {win_rate:.1f}%\n\n"
                
                if best_trades:
                    response += "*Top Winners:*\n"
                    for i, trade in enumerate(best_trades[:3], 1):
                        response += f"{i}. {trade['symbol']}: +${trade['realizedPnl']:,.0f}\n"
                    response += "\n"
                
                response += "*But here's what's costing you:*\n"
            else:
                response += f"💸 *Net Result: -${abs(total_pnl):,.0f}*\n"
                response += f"📊 Win Rate: {win_rate:.1f}%\n\n"
            
            # Show problems for everyone
            if win_rate < 70:
                loss_rate = 100 - win_rate
                response += f"• You lose {loss_rate:.0f}% of your trades\n"
                
            if worst_trades:
                response += f"\n*Worst Disasters:*\n"
                for i, trade in enumerate(worst_trades[:3], 1):
                    response += f"{i}. {trade['symbol']}: -${abs(trade['realizedPnl']):,.0f}\n"
                    
                if total_pnl > 0:
                    # For winners, show impact
                    total_losses = sum(abs(t['realizedPnl']) for t in worst_trades)
                    response += f"\n💡 Fix these and add ${total_losses:,.0f} to your profits"
                else:
                    response += f"\n*These mistakes define your results*"
            
            # Add buttons for next steps
            buttons = [
                [InlineKeyboardButton(
                    "Get specific advice",
                    callback_data=f"advice_{user_id}"
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
            
            # Calculate key metrics for personalized advice
            avg_loss = sum(abs(t['realizedPnl']) for t in worst_trades[:5]) / min(len(worst_trades), 5) if worst_trades else 0
            biggest_loss = abs(worst_trades[0]['realizedPnl']) if worst_trades else 0
            loss_tokens = [t['symbol'] for t in worst_trades[:3]] if worst_trades else []
            
            response = f"*Your Personal Trading Rules*\n\n"
            if total_pnl > 0:
                response += f"You're up ${total_pnl:,.0f} but here's how to keep it:\n\n"
            else:
                response += f"Based on your ${abs(total_pnl):,.0f} loss:\n\n"
            
            # Rule 1 - Position sizing
            response += "*Rule 1: Position Size*\n"
            if total_pnl > 0 and biggest_loss > 5000:
                response += f"• Your {worst_trades[0]['symbol']} loss: -${biggest_loss:,.0f}\n"
                response += f"• Don't let winners make you reckless\n"
                response += f"• Keep max position under ${int(total_pnl * 0.1):,.0f} (10% of profits)\n"
            elif biggest_loss > 10000:
                response += f"• Your {worst_trades[0]['symbol']} disaster: -${biggest_loss:,.0f}\n"
                response += f"• New max position: $300 (not negotiable)\n"
                response += f"• You've proven you can't handle larger sizes\n"
            elif biggest_loss > 5000:
                response += f"• Your worst loss: -${biggest_loss:,.0f}\n"
                response += f"• New max position: $500\n"
                response += f"• Earn the right to trade bigger\n"
            else:
                response += f"• Max position: ${min(1000, biggest_loss * 0.2):,.0f}\n"
                response += f"• That's 20% of your biggest loss\n"
                
            # Rule 2 - Entry rules specific to their patterns
            response += "\n*Rule 2: When You Can Buy*\n"
            if win_rate < 25:
                response += f"• Your {win_rate:.0f}% win rate = you buy tops\n"
                response += f"• Only buy on -15% red days or more\n"
                response += f"• If it's green, you don't touch it\n"
            elif any(token in ['BONK', 'SHIB', 'PEPE', 'WIF', 'DOGE'] for token in loss_tokens):
                response += f"• You lost money on: {', '.join(loss_tokens[:3])}\n"
                response += f"• No more memecoins. Period.\n"
                response += f"• Top 20 market cap only\n"
            else:
                response += f"• Set limit orders 10% below current price\n"
                response += f"• Never market buy again\n"
                response += f"• Patience or poverty\n"
                
            # Rule 3 - Stop losses based on their actual behavior
            response += "\n*Rule 3: Mandatory Stop Losses*\n"
            if avg_loss > 5000:
                response += f"• Your average disaster: -${avg_loss:,.0f}\n"
                response += f"• Stop loss: 5% max (set it before buying)\n"
                response += f"• Break this rule = quit trading\n"
            else:
                response += f"• Stop loss: 7% on every trade\n"
                response += f"• No stop loss = no trade\n"
                response += f"• Your ego isn't worth ${abs(total_pnl):,.0f}\n"
            
            # Rule 4 - Specific behavioral rules
            response += "\n*Rule 4: Your Personal Rules*\n"
            if abs(total_pnl) > 50000:
                response += f"• After losing ${abs(total_pnl):,.0f}, you need supervision\n"
                response += f"• Screenshot every trade plan before entering\n"
                response += f"• If you can't explain it, you can't trade it\n"
            elif worst_trades and len(set(t['symbol'] for t in worst_trades[:5])) == 5:
                response += f"• You jump between too many tokens\n"
                response += f"• Pick 3 tokens max. Master them.\n"
                response += f"• Quality over quantity\n"
            else:
                response += f"• One trade per day maximum\n"
                response += f"• Win or lose, laptop closes after\n"
                response += f"• More trades = more losses for you\n"
                
            response += f"\n📌 *Print this. Follow it. Or stay broke.*"
            
            # Clean up temp database
            temp_db_path = context.user_data.get('temp_db_path')
            if temp_db_path and os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except:
                    pass
            
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
        
        if data.startswith("ex_"):
            # Parse the shortened callback data
            parts = data.split("_")
            symbol = parts[1]
            pnl = float(parts[2])
            
            # Handle the UNK case for large wallets
            if symbol == "UNK":
                # For large wallets without specific trade data
                context.user_data['annotating_symbol'] = "your trades"
                context.user_data['annotating_pnl'] = pnl
                self.user_states[user_id] = WAITING_FOR_ANNOTATION
                
                prompt = (
                    f"Your account shows ${abs(pnl):,.0f} in losses.\n\n"
                    f"Tell me about your trading:\n\n"
                    f"• What types of tokens do you usually buy?\n"
                    f"• Where do you get your trading ideas?\n"
                    f"• What's your biggest trading mistake?\n"
                )
                
                await query.message.reply_text(prompt, parse_mode='Markdown')
            else:
                # Store what we're annotating
                context.user_data['annotating_symbol'] = symbol
                context.user_data['annotating_pnl'] = pnl
                self.user_states[user_id] = WAITING_FOR_ANNOTATION
                
                # Clear, specific prompt about their decision making
                prompt = (
                    f"Tell me about {symbol}:\n\n"
                    f"• Where did you first hear about it?\n"
                    f"• What made you buy at that exact moment?\n"
                    f"• Were you trying to recover from another loss?\n\n"
                    f"(This trade lost ${abs(pnl):,.0f})"
                )
                
                await query.message.reply_text(prompt, parse_mode='Markdown')
            
        elif data.startswith("mistakes_"):
            await self.show_all_mistakes(query.message, user_id, context)
            
        elif data.startswith("advice_"):
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
            
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset user state and clear data"""
        user_id = update.effective_user.id
        
        # Clear user state
        if user_id in self.user_states:
            del self.user_states[user_id]
            
        # Clear any temp database associated with this user
        temp_db_path = context.user_data.get('temp_db_path')
        if temp_db_path and os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except:
                pass
                
        # Clear context data
        context.user_data.clear()
        
        response = (
            "✅ *Reset complete!*\n\n"
            "Your session has been cleared.\n"
            "You can now start fresh.\n\n"
            "Send `/analyze <wallet_address>` to analyze a wallet."
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
            
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        help_text = (
            "*🏥 Tradebro - Learn from your mistakes*\n\n"
            "Commands:\n"
            "• `/analyze <wallet_address>` - Analyze any Solana wallet\n"
            "• /patterns - See your documented patterns\n"
            "• /reset - Clear your session and start fresh\n"
            "• /help - Show this message\n\n"
            "_Example:_\n"
            "`/analyze rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK`\n\n"
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
        application.add_handler(CommandHandler("reset", self.reset_command))
        
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
    bot = TradeBroBot(TOKEN)
    print("🤖 Tradebro Bot starting...")
    bot.run() 