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
from scripts.db_migrations import run_migrations

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
        
        # Run migrations for additional tables
        run_migrations(db)
        
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
            
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        help_text = (
            "*🏥 Tradebro - Wallet Analysis*\n\n"
            "I analyze your trades and show you exactly what went wrong.\n\n"
            "*Commands:*\n"
            "• `/analyze <wallet>` - Analyze any Solana wallet\n"
            "• `/help` - Show this message\n\n"
            "*Example:*\n"
            "`/analyze rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK`\n\n"
            "_One insight at a time. Make it count._"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
            
    def run(self):
        """Start the bot"""
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add handlers - ONLY the essential ones
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("analyze", self.analyze_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
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