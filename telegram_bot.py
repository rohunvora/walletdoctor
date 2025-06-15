#!/usr/bin/env python3
"""
Tradebro Telegram Bot - Learn from your mistakes, avoid repeating them
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
        """Analyze trading data for a wallet address"""
        user_id = update.effective_user.id
        
        # Check if wallet address was provided
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Please provide a wallet address.\n\n"
                "Example:\n"
                "`/analyze rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK`",
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
                # Check if we have partial data
                tables = [t[0] for t in db.execute("SHOW TABLES").fetchall()]
                pnl_count = 0
                if 'pnl' in tables:
                    pnl_count = db.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
                
                error_msg = "Failed to load wallet data.\n\n"
                
                if not os.getenv("HELIUS_KEY") or not os.getenv("CIELO_KEY"):
                    error_msg += "❌ *API keys are missing*\n"
                    error_msg += "The bot needs HELIUS_KEY and CIELO_KEY to fetch data.\n\n"
                    error_msg += "Please run the bot using:\n"
                    error_msg += "`python run_telegram_bot.py`\n\n"
                    error_msg += "Or set your API keys:\n"
                    error_msg += "`export HELIUS_KEY=your_key`\n"
                    error_msg += "`export CIELO_KEY=your_key`"
                elif pnl_count == 0:
                    error_msg += "📊 *No trading data found*\n"
                    error_msg += "This wallet either:\n"
                    error_msg += "• Has never traded on Solana DEXs\n"
                    error_msg += "• Is too new (data not indexed yet)\n"
                    error_msg += "• Only holds tokens (no trades)\n\n"
                    error_msg += "_Try a wallet that has traded on Raydium, Orca, or Jupiter_"
                else:
                    error_msg += "⚠️ *Partial data loaded*\n"
                    error_msg += f"Found {pnl_count} tokens but couldn't complete analysis.\n"
                    error_msg += "This might be due to API rate limits."
                
                await loading_msg.edit_text(error_msg, parse_mode='Markdown')
                db.close()
                # Clean up temp database
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Check if we have data
            tables = [t[0] for t in db.execute("SHOW TABLES").fetchall()]
            
            if 'pnl' not in tables:
                await loading_msg.edit_text(
                    "📊 *No trading data found*\n\n"
                    "This wallet has no trading history on Solana DEXs.\n"
                    "Try a wallet that has traded on Raydium, Orca, or Jupiter.",
                    parse_mode='Markdown'
                )
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
                
            # Get stats using the real data
            instant_gen = InstantStatsGenerator(db)
            stats = instant_gen.get_baseline_stats()
            
            # Check if we hit the token limit first
            token_count = db.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
            hit_limit = token_count >= 100  # Changed from 1000 to 100 to match actual API limit
            
            # Check if 30-day filtering was applied during data loading
            is_30_day_filtered = False
            filter_metadata = None
            try:
                # Check if we have filter metadata
                filter_result = db.execute("""
                    SELECT * FROM filter_metadata 
                    WHERE filter_type = '30_day' 
                    LIMIT 1
                """).fetchone()
                
                if filter_result:
                    is_30_day_filtered = True
                    filter_metadata = {
                        'original_count': filter_result[1],
                        'filtered_count': filter_result[2],
                        'pnl_30d': filter_result[3],
                        'wins_30d': filter_result[4],
                        'losses_30d': filter_result[5],
                        'win_rate_30d': filter_result[6]
                    }
                    original_token_count = filter_result[1]
                    token_count = filter_result[2]
                    
                    # Override stats with 30-day values
                    stats['total_pnl'] = filter_metadata['pnl_30d']
                    stats['win_rate'] = filter_metadata['win_rate_30d']
                    stats['winning_trades'] = filter_metadata['wins_30d']
                    stats['losing_trades'] = filter_metadata['losses_30d']
                    stats['total_trades'] = filter_metadata['wins_30d'] + filter_metadata['losses_30d']
                    
                    logger.info(f"Using 30-day filtered data - PnL: ${filter_metadata['pnl_30d']:,.0f}, Win Rate: {filter_metadata['win_rate_30d']:.1f}%")
            except:
                # Table might not exist, continue with regular logic
                pass
            
            # Check if we have aggregated stats (the TRUE stats from API)
            use_aggregated_stats = False
            aggregated_pnl = 0
            aggregated_win_rate = 0
            
            try:
                # Get the REAL stats from aggregated_stats table
                agg_result = db.execute("""
                    SELECT realized_pnl, win_rate, tokens_traded 
                    FROM aggregated_stats 
                    WHERE wallet_address = ? 
                    LIMIT 1
                """, [wallet_address]).fetchone()
                
                if agg_result:
                    aggregated_pnl = agg_result[0]
                    aggregated_win_rate = agg_result[1] * 100  # Convert to percentage
                    original_token_count = agg_result[2]  # Use real token count
                    use_aggregated_stats = True
                    
                    # Only use aggregated stats if we haven't already applied 30-day filtering
                    if not is_30_day_filtered:
                        # Override the stats with real values
                        stats['total_pnl'] = aggregated_pnl
                        stats['win_rate'] = aggregated_win_rate
                    
                    logger.info(f"Using aggregated stats - PnL: ${aggregated_pnl:,.0f}, Win Rate: {aggregated_win_rate:.1f}%")
                else:
                    logger.warning("No aggregated stats found - using subset data")
            except Exception as e:
                logger.error(f"Error fetching aggregated stats: {e}")
            
            if stats['total_trades'] == 0:
                await loading_msg.edit_text(
                    "📊 *No trades found*\n\n"
                    "This wallet has tokens but no completed trades to analyze.",
                    parse_mode='Markdown'
                )
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Use aggregated stats if available, otherwise fall back to subset
            if use_aggregated_stats:
                # Override the stats with real values
                stats['total_pnl'] = aggregated_pnl
                stats['win_rate'] = aggregated_win_rate
                
                logger.info(f"Using aggregated stats - PnL: ${aggregated_pnl:,.0f}, Win Rate: {aggregated_win_rate:.1f}%, Tokens: {original_token_count}")
            else:
                logger.warning("No aggregated stats found - using subset data")
            
            # Get top trades for analysis with timeout protection
            top_trades = {'winners': [], 'losers': []}
            try:
                # Set a reasonable timeout for getting top trades
                import asyncio
                top_trades = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        instant_gen.get_top_trades, 
                        5
                    ),
                    timeout=3.0  # 3 second timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout getting top trades for large wallet")
                # For large wallets, try to get at least something from the data we have
                try:
                    # Quick query to get at least one winner and loser
                    winner = db.execute("""
                        SELECT symbol, totalPnl as realizedPnl 
                        FROM pnl 
                        WHERE totalPnl > 0 
                        ORDER BY totalPnl DESC 
                        LIMIT 1
                    """).fetchone()
                    
                    loser = db.execute("""
                        SELECT symbol, totalPnl as realizedPnl 
                        FROM pnl 
                        WHERE totalPnl < 0 
                        ORDER BY totalPnl ASC 
                        LIMIT 1
                    """).fetchone()
                    
                    if winner:
                        top_trades['winners'] = [{'symbol': winner[0], 'realizedPnl': winner[1]}]
                    if loser:
                        top_trades['losers'] = [{'symbol': loser[0], 'realizedPnl': loser[1]}]
                except:
                    pass
            except Exception as e:
                logger.error(f"Error getting top trades: {e}")
            
            # Debug log
            logger.info(f"Top trades data: winners={len(top_trades.get('winners', []))}, losers={len(top_trades.get('losers', []))}")
            
            # For large wallets, ensure we have some data even if limited
            if not top_trades.get('winners') and not top_trades.get('losers'):
                # Try to get at least some data from aggregated stats if available
                try:
                    # Check if we have aggregated stats
                    result = db.execute("""
                        SELECT * FROM aggregated_stats 
                        WHERE wallet_address = ? 
                        LIMIT 1
                    """, [wallet_address]).fetchone()
                    
                    if result:
                        logger.info("Using aggregated stats for large wallet")
                except:
                    pass
            
            # Analyze for revenge trading pattern
            revenge_pattern = self.detect_revenge_trading(db, top_trades.get('losers', []))
            
            # Format initial response with accurate context
            if is_30_day_filtered:
                response = f"📊 Found {original_token_count:,} total tokens traded\n"
                response += f"*Analyzing last 30 days* ({token_count} active tokens)\n\n"
            elif use_aggregated_stats and token_count < original_token_count:
                # We have a subset but showing real stats from full wallet
                response = f"📊 *Wallet Overview*\n"
                response += f"• Total tokens traded: {original_token_count}\n"
                response += f"• Showing top {token_count} tokens for analysis\n\n"
            else:
                response = f"📊 Analyzed {token_count} tokens\n\n"
            
            if stats['total_pnl'] < 0:
                response += f"You're down ${abs(stats['total_pnl']):,.0f} with a {stats['win_rate']:.1f}% win rate"
            else:
                response += f"You're up ${stats['total_pnl']:,.0f} with a {stats['win_rate']:.1f}% win rate"
            
            # Add clarification if showing subset with real stats
            if use_aggregated_stats and token_count < original_token_count and not is_30_day_filtered:
                response += f"\n*(Stats reflect all {original_token_count} tokens traded)*"
            
            # Add time context for large wallets
            if is_30_day_filtered:
                response += " *(last 30 days)*"
            
            # Always add a newline before insights
            response += "\n\n"
            
            # Show immediate insight based on detected issues
            insight_added = False
            
            if revenge_pattern and stats['total_pnl'] < 0:
                response += f"🎯 *Your biggest issue: Revenge Trading*\n"
                response += f"After losses, you make bigger, riskier trades.\n"
                if top_trades.get('losers'):
                    worst = top_trades['losers'][0]
                    response += f"Your {worst['symbol']} trade lost ${abs(worst['realizedPnl']):,.0f}.\n\n"
                response += "This behavior has cost you thousands."
                insight_added = True
            elif stats['win_rate'] < 30 and stats['total_pnl'] < 0:
                response += f"🎯 *Your biggest issue: Poor Entry Timing*\n"
                response += f"You're buying at the wrong time.\n"
                response += f"Only {stats['winning_trades']} of {stats['total_trades']} trades made money."
                insight_added = True
            elif stats['avg_pnl'] < -100 and stats['total_pnl'] < 0:
                response += f"🎯 *Your biggest issue: No Risk Management*\n"
                response += f"Your average loss is ${abs(stats['avg_pnl']):,.0f}.\n"
                response += f"You're letting losses run too far."
                insight_added = True
            
            # Always show something for profitable wallets or if no insight was added
            if not insight_added:
                if stats['total_pnl'] > 0:
                    # Profitable wallet - still find issues
                    response += f"💰 *Good, but not great*\n\n"
                    
                    # Show real win rate issues if we have aggregated stats
                    if use_aggregated_stats and stats['win_rate'] < 50:
                        response += f"• Despite profits, your {stats['win_rate']:.1f}% win rate is concerning\n"
                        response += f"• You're losing {100-stats['win_rate']:.0f}% of trades\n"
                    elif stats['win_rate'] < 70:
                        response += f"• {stats['win_rate']:.1f}% win rate leaves room for improvement\n"
                    
                    if top_trades.get('losers'):
                        worst = top_trades['losers'][0]
                        response += f"• Your {worst['symbol']} disaster: -${abs(worst['realizedPnl']):,.0f}\n"
                        response += f"• Even winners shouldn't blow up like this\n\n"
                    elif use_aggregated_stats and stats['win_rate'] < 50:
                        # No losers in subset but poor overall win rate
                        response += f"• Limited data shown, but your losses are real\n"
                        response += f"• Full analysis would reveal your problem trades\n\n"
                    
                    if top_trades.get('winners'):
                        best = top_trades['winners'][0]
                        response += f"Best play: {best['symbol']} +${best['realizedPnl']:,.0f}"
                        if use_aggregated_stats and token_count < original_token_count:
                            response += " *(from visible tokens)*"
                        response += "\n"
                        
                    # For large profitable wallets with no specific trade data, add generic insight
                    if not top_trades.get('winners') and not top_trades.get('losers'):
                        response += f"• With {original_token_count if use_aggregated_stats else stats['total_trades']} tokens traded, you're clearly experienced\n"
                        response += f"• But are you maximizing every opportunity?\n"
                        response += f"• Even pros have blind spots\n"
                else:
                    # Catch-all for any other negative PnL cases
                    response += f"🎯 *Time for a reality check*\n"
                    response += f"Your trading needs serious work.\n"
                    response += f"Let's fix what's broken."
            
            await loading_msg.edit_text(response, parse_mode='Markdown')
            
            # ALWAYS offer deeper analysis - simplified to ensure it works
            try:
                # Debug log
                logger.info(f"About to show follow-up buttons for wallet with {stats['total_trades']} trades, PnL: {stats['total_pnl']}")
                
                # Small delay for better UX
                import asyncio
                await asyncio.sleep(1.0)
                
                # Simplified button creation
                buttons = []
                
                # For profitable wallets, don't show loss button
                if stats['total_pnl'] < 0:
                    # Try to add specific loss button if we have data
                    if top_trades and top_trades.get('losers') and len(top_trades['losers']) > 0:
                        worst_loss = top_trades['losers'][0]
                        if 'symbol' in worst_loss and 'realizedPnl' in worst_loss:
                            symbol_short = str(worst_loss['symbol'])[:10]
                            pnl_k = int(abs(worst_loss['realizedPnl']) / 1000)  # Convert to thousands
                            buttons.append([InlineKeyboardButton(
                                f"Why did I lose ${abs(worst_loss['realizedPnl']):,.0f} on {worst_loss['symbol']}?",
                                callback_data=f"ex_{symbol_short}_{pnl_k}k"
                            )])
                    
                    # If no specific loss data, add generic button
                    if not buttons:
                        total_loss_k = int(abs(stats['total_pnl']) / 1000)
                        buttons.append([InlineKeyboardButton(
                            "Why am I losing money?",
                            callback_data=f"ex_UNK_{total_loss_k}k"
                        )])
                
                # Always show these buttons - simplified IDs
                buttons.extend([
                    [InlineKeyboardButton(
                        "Show detailed breakdown",
                        callback_data=f"mistakes_{str(user_id)[-8:]}"  # Last 8 digits of user ID
                    )],
                    [InlineKeyboardButton(
                        "Get personalized rules",
                        callback_data=f"advice_{str(user_id)[-8:]}"  # Last 8 digits of user ID
                    )]
                ])
                
                reply_markup = InlineKeyboardMarkup(buttons)
                
                # Simple follow-up message
                if stats['total_pnl'] > 0:
                    followup_msg = "You're profitable, but are you maximizing?\n\nLet me show you what's holding you back."
                else:
                    followup_msg = "Want to understand what's going wrong?\n\nI can show you exactly why you're losing money."
                
                logger.info(f"Sending follow-up message with {len(buttons)} buttons")
                
                # Send the follow-up message
                await update.message.reply_text(
                    followup_msg,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                logger.info("Follow-up message sent successfully")
                
                # Store analysis data for later use - ensure we handle missing data
                context.user_data['current_wallet'] = wallet_address
                context.user_data['total_pnl'] = stats.get('total_pnl', 0)
                context.user_data['win_rate'] = stats.get('win_rate', 0)
                context.user_data['worst_trades'] = top_trades.get('losers', [])[:5] if top_trades else []
                context.user_data['best_trades'] = top_trades.get('winners', [])[:5] if top_trades else []
                context.user_data['temp_db_path'] = temp_db_path
                context.user_data['is_large_wallet'] = hit_limit
                
            except Exception as e:
                logger.error(f"Error showing follow-up buttons: {e}")
                logger.error(f"Stats: {stats}")
                logger.error(f"Top trades: {top_trades}")
                import traceback
                logger.error(traceback.format_exc())
                
                # Still try to show basic follow-up
                try:
                    await update.message.reply_text(
                        "Want personalized trading advice?\n\nType `/help` to see available commands.",
                        parse_mode='Markdown'
                    )
                except Exception as e2:
                    logger.error(f"Even basic follow-up failed: {e2}")
            
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