#!/usr/bin/env python3
"""
Tradebro Bot - Simplified version focused on one perfect insight
"""

import os
import logging
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, filters, ContextTypes
import duckdb
import asyncio

# Set up logging
from scripts.data import load_wallet
from scripts.instant_stats import InstantStatsGenerator
from scripts.creative_trade_labels import format_telegram_report_card
from scripts.grading_engine import TradingGrader
from scripts.analytics import get_wallet_stats_smart
from scripts.transaction_parser import TransactionParser, SwapTransaction
from scripts.notification_engine import NotificationEngine
from scripts.monitoring_manager import get_monitoring_manager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TradeBroBot:
    def __init__(self, token: str, db_path: str = "coach.db"):
        self.token = token
        self.db_path = db_path
        self.monitoring_manager = None
        
        # Initialize main database
        db = duckdb.connect(db_path)
        self.init_db(db)
        db.close()
        
    def init_db(self, db):
        """Initialize database schema"""
        # Create core tables needed by load_wallet
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
        
        # Additional tables created as needed
        
        # Ensure annotations table exists
        db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_annotations (
                user_id BIGINT,
                symbol VARCHAR,
                pnl DOUBLE,
                annotation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ensure filters table exists for wallet metadata
        db.execute("""
            CREATE TABLE IF NOT EXISTS filter_metadata (
                wallet_address TEXT PRIMARY KEY,
                filter_applied TEXT,
                filter_timestamp TIMESTAMP,
                is_30_day_filtered BOOLEAN
            )
        """)
        
        # Monitoring tables for Phase 1
        db.execute("""
            CREATE TABLE IF NOT EXISTS monitored_wallets (
                user_id BIGINT,
                wallet_address TEXT,
                wallet_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                PRIMARY KEY (user_id, wallet_address)
            )
        """)
        
        db.execute("""
            CREATE TABLE IF NOT EXISTS wallet_transactions (
                tx_signature TEXT PRIMARY KEY,
                wallet_address TEXT,
                timestamp BIGINT,
                action TEXT,
                token_in TEXT,
                token_out TEXT,
                amount_in DECIMAL,
                amount_out DECIMAL,
                dex TEXT,
                program_id TEXT,
                slot BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
            
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - show welcome message"""
        welcome = (
            "👋 *Welcome to Tradebro*\n\n"
            "I analyze your trades and show you exactly why you're losing money.\n\n"
            "Send me a wallet:\n"
            "`/analyze <wallet_address>`\n\n"
            "Example:\n"
            "`/analyze rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK`"
        )
        
        await update.message.reply_text(welcome, parse_mode='Markdown')
        
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
            
            # Get REAL stats from aggregated data FIRST
            aggregated_stats = None
            try:
                agg_result = db.execute("""
                    SELECT realized_pnl, win_rate, tokens_traded 
                    FROM aggregated_stats 
                    WHERE wallet_address = ? 
                    LIMIT 1
                """, [wallet_address]).fetchone()
                
                if agg_result:
                    aggregated_stats = {
                        'total_pnl': agg_result[0],
                        'win_rate': agg_result[1] * 100,
                        'tokens_traded': agg_result[2]
                    }
                    logger.info(f"Using aggregated stats: PnL=${agg_result[0]:,.0f}, Tokens={agg_result[2]}")
            except Exception as e:
                logger.info(f"No aggregated stats available: {e}")
            
            # Debug: Check specific tokens we know should be losses
            gm_check = db.execute("SELECT symbol, totalPnl, realizedPnl FROM pnl WHERE symbol = 'gm'").fetchall()
            rlms_check = db.execute("SELECT symbol, totalPnl, realizedPnl FROM pnl WHERE symbol = 'RLMS'").fetchall()
            logger.info(f"gm data: {gm_check}")
            logger.info(f"RLMS data: {rlms_check}")
            
            # Check data structure
            sample_check = db.execute("SELECT symbol, totalPnl, realizedPnl FROM pnl ORDER BY realizedPnl ASC LIMIT 10").fetchall()
            logger.info(f"Sample by realizedPnl: {sample_check}")
            
            # Check what columns actually exist in the table
            columns_check = db.execute("PRAGMA table_info(pnl)").fetchall()
            logger.info(f"PnL table columns: {[col[1] for col in columns_check]}")
            
            # Try finding losses with normalized field names
            recent_losses_query = """
                SELECT 
                    symbol,
                    totalPnl as pnl,
                    avgBuyPrice as buy_price,
                    avgSellPrice as sell_price,
                    totalBought as bought,
                    totalSold as sold,
                    numSwaps as swaps
                FROM pnl
                WHERE totalPnl < -500
                ORDER BY totalPnl ASC
                LIMIT 10
            """
            
            losses = db.execute(recent_losses_query).fetchall()
            logger.info(f"Found {len(losses)} losses using realizedPnl")
            
            if not losses:
                # First check what data we're working with
                token_count = db.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
                
                # Use aggregated stats if available, otherwise use subset
                if aggregated_stats:
                    api_total = aggregated_stats['total_pnl']
                    total_tokens = aggregated_stats['tokens_traded']
                    win_rate = aggregated_stats['win_rate']
                    
                    # Calculate how many tokens are hidden
                    hidden_tokens = total_tokens - token_count if total_tokens > token_count else 0
                    losing_tokens_estimate = int(total_tokens * (1 - win_rate/100))
                    
                    response = f"Your last 30 days: ${api_total:,.0f} profit.\n\n"
                    
                    if hidden_tokens > 0:
                        response += f"But here's the problem:\n"
                        response += f"• You traded {total_tokens} tokens\n"
                        response += f"• API only shows top {token_count} winners\n"
                        response += f"• {hidden_tokens} tokens hidden (likely all losses)\n"
                        response += f"• With {win_rate:.0f}% win rate = ~{losing_tokens_estimate} losers\n\n"
                        response += "Your losses exist. They're just buried.\n"
                        response += "The API won't show tokens ranked 101-768."
                    else:
                        response += f"Showing all {token_count} tokens traded.\n"
                        response += "No losses found in your recent trades."
                else:
                    subset_total = db.execute("SELECT SUM(totalPnl) FROM pnl").fetchone()[0]
                    response = f"Recent trading: ${subset_total:,.0f}\n\n"
                    response += f"From {token_count} tokens analyzed.\n\n"
                    response += "Limited data available."
                
                await loading_msg.edit_text(response)
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Analyze the most impactful loss
            symbol, pnl, buy_price, sell_price, bought, sold, swaps = losses[0]
            
            # Get 30-day context
            if aggregated_stats:
                total_context = f"Your last 30 days: ${aggregated_stats['total_pnl']:,.0f} profit.\n\n"
            else:
                total_context = ""
            
            # Calculate what happened
            if sell_price and sell_price > 0 and buy_price and buy_price > 0:
                # They sold at a loss
                drop_pct = ((sell_price - buy_price) / buy_price) * 100
                
                # Look for pump chasing pattern
                if drop_pct < -50:  # Lost more than 50%
                    response = total_context
                    response += f"But you lost ${abs(pnl):,.0f} on {symbol}.\n\n"
                    response += f"Down {abs(drop_pct):.0f}%. Classic pump chase.\n\n"
                    response += "You buy excitement. You sell regret."
                    
                elif swaps and swaps > 10:  # Overtrading
                    response = total_context
                    response += f"You lost ${abs(pnl):,.0f} on {symbol}.\n\n"
                    response += f"{swaps} trades on one token. Each one making it worse.\n\n"
                    response += "Overtrading is revenge trading in disguise."
                    
                else:  # Generic bad timing
                    response = total_context
                    response += f"Your {symbol} trade: -${abs(pnl):,.0f}\n\n"
                    if buy_price > 0:
                        response += f"Bought at ${buy_price:.6f}"
                        if sell_price > 0:
                            response += f", sold at ${sell_price:.6f}"
                        response += "\n\n"
                    response += "Bad entry. Worse exit."
            else:
                # Missing price data or still holding
                response = total_context
                response += f"You're down ${abs(pnl):,.0f} on {symbol}.\n\n"
                if sell_price == 0 or not sell_price:
                    response += "Still holding. Still hoping.\n\n"
                    response += "Hope isn't a strategy."
                else:
                    response += "Another failed trade.\n\n"
                    response += "The pattern is clear."
            
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
            
    async def grade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate a trading report card with creative labels"""
        if not update.message or not context.args:
            await update.message.reply_text("Please provide a wallet address: `/grade <address>`", parse_mode='Markdown')
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
        temp_db_path = f"/tmp/tradebro_grade_{user_id}_{int(time.time())}.db"
        
        # Send loading message
        loading_msg = await update.message.reply_text("📊 Generating your trading report card...")
        
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
            
            # Get wallet stats for grading
            stats = get_wallet_stats_smart(db)
            
            if stats['total_tokens_traded'] == 0:
                await loading_msg.edit_text("📊 *No trades found for grading*")
                db.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return
            
            # Generate grade
            grader = TradingGrader()
            grade_report = grader.generate_grade_report(stats)
            
            # Get trades for creative labels
            trades_df = db.execute("SELECT * FROM pnl ORDER BY ABS(totalPnl) DESC LIMIT 10").fetchall()
            
            # Convert to list of dicts
            column_names = [desc[0] for desc in db.execute("SELECT * FROM pnl LIMIT 0").description]
            trades = []
            for row in trades_df:
                trade_dict = dict(zip(column_names, row))
                trades.append(trade_dict)
            
            # Generate the ASCII report card
            if trades:
                report_card = format_telegram_report_card(
                    grade=grade_report['grade'],
                    percentile=grade_report['percentile'],
                    trades=trades,
                    stats=stats
                )
                
                # Send the report card (using monospace formatting)
                await loading_msg.edit_text(f"```\n{report_card}\n```", parse_mode='Markdown')
                
                # Store for potential future use
                context.user_data['last_grade'] = {
                    'wallet': wallet_address,
                    'grade': grade_report['grade'],
                    'percentile': grade_report['percentile'],
                    'timestamp': datetime.now()
                }
            else:
                # Fallback to simple grade if no trades
                simple_report = f"""
Your Trading Grade: {grade_report['grade']}
Better than {grade_report['percentile']}% of traders

{grade_report['insights']['grade_message']}

Superpower: {grade_report['insights']['superpower']}
Kryptonite: {grade_report['insights']['kryptonite']}
"""
                await loading_msg.edit_text(simple_report)
            
            db.close()
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
                
        except Exception as e:
            logger.error(f"Error in grade command: {e}")
            await loading_msg.edit_text(f"Error generating grade: {str(e)}")
            # Clean up on error
            try:
                if 'db' in locals():
                    db.close()
                if 'temp_db_path' in locals() and os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
            except:
                pass

    async def monitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start monitoring a wallet for real-time swap notifications"""
        if not update.message or len(context.args) < 1:
            await update.message.reply_text(
                "Please provide a wallet address: `/monitor <wallet_address> [wallet_name]`",
                parse_mode='Markdown'
            )
            return
            
        wallet_address = context.args[0]
        wallet_name = context.args[1] if len(context.args) > 1 else None
        user_id = update.effective_user.id
        
        # Validate Solana address
        try:
            if len(wallet_address) < 32 or len(wallet_address) > 44:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid Solana wallet address")
            return
        
        try:
            # Connect to main database
            db = duckdb.connect(self.db_path)
            
            # Check if already monitoring
            existing = db.execute("""
                SELECT wallet_name FROM monitored_wallets 
                WHERE user_id = ? AND wallet_address = ? AND is_active = TRUE
            """, [user_id, wallet_address]).fetchone()
            
            if existing:
                await update.message.reply_text(
                    f"📊 Already monitoring wallet: {existing[0] or wallet_address[:8]}..."
                )
                db.close()
                return
            
            # Add to monitoring list
            db.execute("""
                INSERT OR REPLACE INTO monitored_wallets 
                (user_id, wallet_address, wallet_name, is_active)
                VALUES (?, ?, ?, TRUE)
            """, [user_id, wallet_address, wallet_name])
            
            db.close()
            
            # Send confirmation
            display_name = wallet_name or f"{wallet_address[:8]}..."
            await update.message.reply_text(
                f"✅ **Monitoring Started**\n\n"
                f"📊 Wallet: {display_name}\n"
                f"🔔 You'll get notified of all swaps\n\n"
                f"Use `/unmonitor {wallet_address}` to stop",
                parse_mode='Markdown'
            )
            
            # Start actual monitoring
            if not self.monitoring_manager:
                self.monitoring_manager = await get_monitoring_manager(self.db_path, self.token)
            
            await self.monitoring_manager.add_wallet_monitoring(user_id, wallet_address, wallet_name)
            
        except Exception as e:
            logger.error(f"Error in monitor command: {e}")
            await update.message.reply_text(f"Error starting monitoring: {str(e)}")
    
    async def unmonitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop monitoring a wallet"""
        if not update.message or not context.args:
            await update.message.reply_text(
                "Please provide a wallet address: `/unmonitor <wallet_address>`",
                parse_mode='Markdown'
            )
            return
            
        wallet_address = context.args[0]
        user_id = update.effective_user.id
        
        try:
            db = duckdb.connect(self.db_path)
            
            # Check if monitoring
            existing = db.execute("""
                SELECT wallet_name FROM monitored_wallets 
                WHERE user_id = ? AND wallet_address = ? AND is_active = TRUE
            """, [user_id, wallet_address]).fetchone()
            
            if not existing:
                await update.message.reply_text("❌ Not monitoring this wallet")
                db.close()
                return
            
            # Remove from monitoring
            db.execute("""
                UPDATE monitored_wallets 
                SET is_active = FALSE 
                WHERE user_id = ? AND wallet_address = ?
            """, [user_id, wallet_address])
            
            db.close()
            
            display_name = existing[0] or f"{wallet_address[:8]}..."
            await update.message.reply_text(
                f"✅ **Monitoring Stopped**\n\n"
                f"📊 Wallet: {display_name}\n"
                f"🔕 No more notifications",
                parse_mode='Markdown'
            )
            
            # Remove from actual monitoring
            if self.monitoring_manager:
                await self.monitoring_manager.remove_wallet_monitoring(wallet_address)
            
        except Exception as e:
            logger.error(f"Error in unmonitor command: {e}")
            await update.message.reply_text(f"Error stopping monitoring: {str(e)}")
    
    async def monitoring_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all monitored wallets"""
        user_id = update.effective_user.id
        
        try:
            db = duckdb.connect(self.db_path)
            
            wallets = db.execute("""
                SELECT wallet_address, wallet_name, created_at 
                FROM monitored_wallets 
                WHERE user_id = ? AND is_active = TRUE
                ORDER BY created_at DESC
            """, [user_id]).fetchall()
            
            db.close()
            
            if not wallets:
                await update.message.reply_text(
                    "📊 **No wallets being monitored**\n\n"
                    "Use `/monitor <wallet_address>` to start tracking",
                    parse_mode='Markdown'
                )
                return
            
            message = "📊 **Your Monitored Wallets:**\n\n"
            for wallet_addr, wallet_name, created_at in wallets:
                display_name = wallet_name or f"{wallet_addr[:8]}..."
                message += f"• {display_name}\n"
                message += f"  `{wallet_addr}`\n\n"
            
            message += f"Total: {len(wallets)} wallets\n"
            message += "Use `/unmonitor <address>` to stop tracking"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in monitoring command: {e}")
            await update.message.reply_text(f"Error fetching monitored wallets: {str(e)}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        help_text = (
            "*🏥 Tradebro - Wallet Analysis*\n\n"
            "I analyze your trades and show you exactly what went wrong.\n\n"
            "*Commands:*\n"
            "• `/analyze <wallet>` - Get one brutal insight\n"
            "• `/grade <wallet>` - Get your trading report card\n"
            "• `/monitor <wallet> [name]` - Track wallet in real-time\n"
            "• `/unmonitor <wallet>` - Stop tracking wallet\n"
            "• `/monitoring` - Show tracked wallets\n"
            "• `/help` - Show this message\n\n"
            "*Examples:*\n"
            "`/analyze rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK`\n"
            "`/grade rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK`\n"
            "`/monitor rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK POW`\n\n"
            "_One insight at a time. Make it count._"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
            
    async def _init_monitoring_on_startup(self):
        """Initialize monitoring manager on bot startup if there are wallets to monitor"""
        try:
            db = duckdb.connect(self.db_path)
            wallets = db.execute("""
                SELECT COUNT(*) FROM monitored_wallets WHERE is_active = TRUE
            """).fetchone()[0]
            db.close()
            
            if wallets > 0:
                logger.info(f"Found {wallets} wallets to monitor, starting monitoring manager...")
                self.monitoring_manager = await get_monitoring_manager(self.db_path, self.token)
            else:
                logger.info("No wallets to monitor on startup")
                
        except Exception as e:
            logger.error(f"Error initializing monitoring on startup: {e}")
    
    def run(self):
        """Start the bot"""
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add handlers - Essential commands
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("analyze", self.analyze_command))
        application.add_handler(CommandHandler("grade", self.grade_command))
        application.add_handler(CommandHandler("monitor", self.monitor_command))
        application.add_handler(CommandHandler("unmonitor", self.unmonitor_command))
        application.add_handler(CommandHandler("monitoring", self.monitoring_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
        # Add post-init hook to start monitoring
        async def post_init(app):
            await self._init_monitoring_on_startup()
        
        application.post_init = post_init
        
        # Run the bot
        logger.info("🤖 Tradebro Bot starting...")
        application.run_polling()

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
    bot.run() 