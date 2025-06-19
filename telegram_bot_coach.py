#!/usr/bin/env python3
"""
Pocket Trading Coach - Conversational real-time trading coach
Asks questions, remembers answers, learns from responses
"""

import os
import logging
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import duckdb
import asyncio
from typing import Dict, List, Optional
import statistics

# Import existing modules we can reuse
from scripts.data import load_wallet
from scripts.transaction_parser import TransactionParser, SwapTransaction
from scripts.token_metadata import TokenMetadataService
from scripts.link_generator import LinkGenerator
from scripts.price_service import PriceService
from scripts.notification_engine import NotificationEngine
from scripts.pnl_service import FastPnLService

# Import GPT client
from gpt_client import create_gpt_client

# Import prompt builder and diary API
from prompt_builder import write_to_diary, build_prompt
from diary_api import invalidate_cache

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Legacy pattern detection classes removed - now using swappable architecture
# See nudge_engine.py, pattern_service.py, and conversation_manager.py


class PocketCoachBot:
    def __init__(self, token: str, db_path: str = "pocket_coach.db"):
        self.token = token
        self.db_path = db_path
        self.monitoring_tasks = {}  # user_id -> asyncio.Task
        self.token_metadata_service = TokenMetadataService()
        self.price_service = PriceService()
        
        # Initialize P&L service
        self.pnl_service = FastPnLService(
            cielo_api_key="7c855165-3874-4237-9416-450d2373ea72",
            birdeye_api_key="4e5e878a6137491bbc280c10587a0cce"
        )
        
        # Initialize notification engine with P&L service
        self.notification_engine = NotificationEngine(pnl_service=self.pnl_service)
        
        # Initialize database
        self.init_db()
        
        # Initialize GPT client
        self.gpt_client = create_gpt_client(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-mini",
            timeout=10.0
        )
        
        # Log initialization status
        if self.gpt_client.is_available():
            logger.info("GPT client initialized successfully")
        else:
            logger.warning("GPT client not available - check OPENAI_API_KEY environment variable")
        
        logger.info("Pocket Trading Coach initialized with lean pipeline")
    
    def init_db(self):
        """Initialize database schema"""
        db = duckdb.connect(self.db_path)
        
        # User wallets table
        db.execute("""
            CREATE TABLE IF NOT EXISTS user_wallets (
                user_id BIGINT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # User trades history
        db.execute("""
            CREATE SEQUENCE IF NOT EXISTS user_trades_seq START 1;
            CREATE TABLE IF NOT EXISTS user_trades (
                id INTEGER PRIMARY KEY DEFAULT nextval('user_trades_seq'),
                user_id BIGINT,
                wallet_address TEXT,
                tx_signature TEXT,
                timestamp TIMESTAMP,
                action TEXT,
                token_address TEXT,
                token_symbol TEXT,
                sol_amount DECIMAL,
                token_amount DECIMAL,
                entry_price DECIMAL,
                current_price DECIMAL,
                pnl_usd DECIMAL,
                pnl_percent DECIMAL,
                hold_time_minutes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Recent transactions tracking
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
        
        # Trade notes for learning
        db.execute("""
            CREATE SEQUENCE IF NOT EXISTS trade_notes_seq START 1;
            CREATE TABLE IF NOT EXISTS trade_notes (
                id INTEGER PRIMARY KEY DEFAULT nextval('trade_notes_seq'),
                user_id BIGINT,
                tx_signature TEXT,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        db.close()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - show welcome message"""
        welcome = (
            "👋 *Welcome to Your Pocket Trading Coach*\n\n"
            "I watch your trades in real-time and nudge you—with receipts—"
            "to make better decisions.\n\n"
            "Connect your wallet to start:\n"
            "`/connect <wallet_address>`\n\n"
            "Example:\n"
            "`/connect 34zYDg...VCya`\n\n"
            "_No predictions. No whale alerts. Just facts from YOUR history._"
        )
        
        await update.message.reply_text(welcome, parse_mode='Markdown')
    
    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Connect user's wallet for personal monitoring"""
        if not update.message or not context.args:
            await update.message.reply_text("Please provide your wallet address: `/connect <address>`", parse_mode='Markdown')
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
        
        # Connect to database
        db = duckdb.connect(self.db_path)
        
        try:
            # Check if already connected
            existing = db.execute("""
                SELECT wallet_address FROM user_wallets
                WHERE user_id = ?
            """, [user_id]).fetchone()
            
            if existing:
                # Update wallet
                db.execute("""
                    UPDATE user_wallets
                    SET wallet_address = ?, connected_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, [wallet_address, user_id])
                message = f"✅ Updated your wallet to `{wallet_address[:8]}...{wallet_address[-4:]}`"
            else:
                # Insert new connection
                db.execute("""
                    INSERT INTO user_wallets (user_id, wallet_address)
                    VALUES (?, ?)
                """, [user_id, wallet_address])
                message = f"✅ Connected to wallet `{wallet_address[:8]}...{wallet_address[-4:]}`"
            
            db.commit()
            
            # Start monitoring
            await self._start_monitoring_for_user(user_id, wallet_address)
            
            message += "\n\nI'm now watching your trades. Make a swap and I'll analyze it instantly."
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error connecting wallet: {e}")
            await update.message.reply_text("❌ Error connecting wallet. Please try again.")
        finally:
            db.close()
    
    async def disconnect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disconnect wallet and stop monitoring"""
        user_id = update.effective_user.id
        
        # Stop monitoring
        if user_id in self.monitoring_tasks:
            self.monitoring_tasks[user_id].cancel()
            del self.monitoring_tasks[user_id]
        
        # Update database
        db = duckdb.connect(self.db_path)
        try:
            db.execute("""
                UPDATE user_wallets
                SET is_active = FALSE
                WHERE user_id = ?
            """, [user_id])
            db.commit()
            
            await update.message.reply_text("✅ Disconnected. Your wallet is no longer being monitored.")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            await update.message.reply_text("❌ Error disconnecting wallet.")
        finally:
            db.close()
    
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a note to the most recent trade"""
        if not context.args:
            await update.message.reply_text("Usage: `/note <your note about the trade>`", parse_mode='Markdown')
            return
        
        user_id = update.effective_user.id
        note = ' '.join(context.args)
        
        db = duckdb.connect(self.db_path)
        try:
            # Get most recent trade
            result = db.execute("""
                SELECT tx_signature
                FROM user_trades
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, [user_id]).fetchone()
            
            if not result:
                await update.message.reply_text("❌ No recent trades found to annotate.")
                return
            
            tx_signature = result[0]
            
            # Store note
            db.execute("""
                INSERT INTO trade_notes (user_id, tx_signature, note)
                VALUES (?, ?, ?)
            """, [user_id, tx_signature, note])
            db.commit()
            
            await update.message.reply_text("✅ Note added. I'll learn from this.")
            
        except Exception as e:
            logger.error(f"Error adding note: {e}")
            await update.message.reply_text("❌ Error adding note.")
        finally:
            db.close()
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's trading statistics"""
        user_id = update.effective_user.id
        
        db = duckdb.connect(self.db_path)
        try:
            # Get basic stats
            result = db.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(pnl_usd) as total_pnl,
                    AVG(sol_amount) as avg_size,
                    AVG(CASE WHEN pnl_usd > 0 THEN hold_time_minutes ELSE NULL END) as avg_winner_hold
                FROM user_trades
                WHERE user_id = ?
            """, [user_id]).fetchone()
            
            if not result or result[0] == 0:
                await update.message.reply_text("📊 No trades recorded yet. Make a swap to start tracking!")
                return
            
            total_trades, wins, total_pnl, avg_size, avg_winner_hold = result
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            stats_message = f"""
📊 *Your Trading Stats*

Total Trades: {total_trades}
Win Rate: {win_rate:.1f}%
Total P&L: ${total_pnl:,.2f}
Avg Position: {avg_size:.2f} SOL
Avg Winner Hold: {avg_winner_hold:.0f} min

_Based on your actual trading history._
"""
            
            await update.message.reply_text(stats_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            await update.message.reply_text("❌ Error retrieving stats.")
        finally:
            db.close()
    
    async def handle_note_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == 'skip':
            # User chose to skip
            await query.edit_message_text(
                text=query.message.text + "\n\n_Skipped_",
                parse_mode='Markdown'
            )
            
        elif query.data.startswith('note:'):
            # Legacy button handling (kept for compatibility)
            response_type = query.data.split(':', 1)[1]
            
            if response_type == 'other':
                # In text-first mode, this shouldn't happen often
                await query.edit_message_text(
                    text=query.message.text + "\n\n💭 Type your response below:",
                    parse_mode='Markdown'
                )
            else:
                # Legacy response handling
                await query.edit_message_text(
                    text=query.message.text + f"\n\n✅ Got it: '{response_type.replace('_', ' ')}' 📝",
                    parse_mode='Markdown'
                )
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages with lean pipeline and GPT tools"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        logger.info(f"Received text message from user {user_id}: '{message_text}'")
        
        # Import prompt builder
        from prompt_builder import write_to_diary, build_prompt
        import json
        
        try:
            # Get wallet address for user
            db = duckdb.connect(self.db_path)
            result = db.execute("""
                SELECT wallet_address FROM user_wallets 
                WHERE user_id = ? AND is_active = TRUE
            """, [user_id]).fetchone()
            db.close()
            
            wallet_address = result[0] if result else None
            
            # Write message to diary
            await write_to_diary('message', user_id, wallet_address, {'text': message_text})
            
            # Show typing indicator
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            
            # Build minimal prompt
            prompt_data = await build_prompt(user_id, wallet_address, 'message', {'text': message_text})
            
            # Load Coach L prompt
            with open('coach_prompt_v1.md', 'r') as f:
                coach_prompt = f.read()
            
            # Get GPT response with tools
            response = await self.gpt_client.chat_with_tools(
                system_prompt=coach_prompt,
                user_message=json.dumps(prompt_data),
                tools=self._get_gpt_tools(),
                wallet_address=wallet_address  # For tool execution
            )
            
            if response:
                # Write response to diary
                await write_to_diary('response', user_id, wallet_address, {'text': response})
                
                # Send response
                await update.message.reply_text(response)
                logger.info(f"Sent GPT response: '{response[:50]}...'")
            else:
                # Fallback if no response
                await update.message.reply_text("Sorry, I'm having trouble processing that. Try again in a moment.")
                
        except Exception as e:
            logger.error(f"Error processing message from user {user_id}: {e}")
            await update.message.reply_text("Sorry, I'm having trouble processing that. Try again in a moment.")
    
    async def _start_monitoring_for_user(self, user_id: int, wallet_address: str):
        """Start monitoring a user's wallet"""
        # Cancel existing task if any
        if user_id in self.monitoring_tasks:
            self.monitoring_tasks[user_id].cancel()
        
        # Create new monitoring task
        task = asyncio.create_task(self._monitor_wallet(user_id, wallet_address))
        self.monitoring_tasks[user_id] = task
    
    async def _fetch_recent_transactions(self, wallet_address: str, limit: int = 10) -> List[dict]:
        """Fetch recent transactions for a wallet"""
        try:
            parser = TransactionParser()
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    wallet_address,
                    {"limit": limit}
                ]
            }
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(parser.rpc_url, json=payload) as response:
                    result = await response.json()
                    return result.get("result", [])
                    
        except Exception as e:
            logger.error(f"Error fetching recent transactions: {e}")
            return []
    
    async def _get_sol_balance(self, wallet_address: str) -> float:
        """Get SOL balance via RPC"""
        try:
            import aiohttp
            # Use Helius RPC for balance query
            helius_key = os.getenv('HELIUS_KEY')
            rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_key}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [wallet_address]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(rpc_url, json=payload) as response:
                    result = await response.json()
                    if 'result' in result:
                        # Convert lamports to SOL
                        lamports = result['result']['value']
                        return lamports / 1_000_000_000
                    else:
                        logger.error(f"Error getting balance: {result}")
                        return 0.0
                        
        except Exception as e:
            logger.error(f"Error fetching SOL balance: {e}")
            return 0.0
    
    async def _monitor_wallet(self, user_id: int, wallet_address: str):
        """Monitor a wallet for new transactions"""
        parser = TransactionParser()
        
        # Wait for application to be ready
        while not hasattr(self, 'application'):
            await asyncio.sleep(1)
        
        app = self.application
        
        # Get last processed signature
        db = duckdb.connect(self.db_path)
        result = db.execute("""
            SELECT tx_signature
            FROM wallet_transactions
            WHERE wallet_address = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, [wallet_address]).fetchone()
        
        last_signature = result[0] if result else None
        db.close()
        
        while True:
            try:
                # Fetch recent transactions using RPC
                transactions = await self._fetch_recent_transactions(wallet_address, limit=10)
                
                new_transactions = []
                for tx in transactions:
                    if tx['signature'] == last_signature:
                        break
                    new_transactions.append(tx)
                
                if new_transactions:
                    logger.info(f"Found {len(new_transactions)} new transactions for {wallet_address[:8]}...")
                
                # Process new transactions
                for tx in reversed(new_transactions):  # Process oldest first
                    # Parse the full transaction
                    parsed = await parser.parse_transaction(tx['signature'])
                    if parsed:
                        await self._process_swap(user_id, wallet_address, parsed, app)
                    last_signature = tx['signature']
                
                # Wait before next check
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring wallet {wallet_address}: {e}")
                await asyncio.sleep(30)  # Wait longer on error
    
    async def _process_swap(self, user_id: int, wallet_address: str, swap: SwapTransaction, app):
        """Process a swap transaction with bankroll tracking and diary writing"""
        logger.info(f"Processing {swap.action} swap: {swap.signature[:8]}...")
        
        # Import prompt builder
        from prompt_builder import write_to_diary, build_prompt
        from diary_api import invalidate_cache
        import json
        
        try:
            # 1. Get bankroll BEFORE trade
            bankroll_before_sol = await self._get_sol_balance(wallet_address)
            logger.info(f"Bankroll before: {bankroll_before_sol:.4f} SOL")
            
            # 2. Determine token info based on action
            if swap.action == 'BUY':
                token_address = swap.token_out
                sol_amount = swap.amount_in  # SOL spent
                token_amount = swap.amount_out
            else:  # SELL
                token_address = swap.token_in
                sol_amount = swap.amount_out  # SOL received
                token_amount = swap.amount_in
            
            # Get token metadata
            token_metadata = await self.token_metadata_service.get_token_metadata(token_address)
            token_symbol = token_metadata.symbol if token_metadata else 'Unknown'
            
            # 3. Calculate bankroll after and trade percentage
            if swap.action == 'BUY':
                bankroll_after_sol = bankroll_before_sol - sol_amount
            else:  # SELL
                bankroll_after_sol = bankroll_before_sol + sol_amount
            
            # Calculate exact percentage (no rounding as per requirement)
            trade_pct_bankroll = (sol_amount / bankroll_before_sol) * 100 if bankroll_before_sol > 0 else 0
            
            # 4. Prepare complete trade data for diary
            trade_data = {
                'signature': swap.signature,
                'action': swap.action,
                'token_symbol': token_symbol,
                'token_address': token_address,
                'sol_amount': sol_amount,
                'token_amount': token_amount,
                'bankroll_before_sol': bankroll_before_sol,
                'bankroll_after_sol': bankroll_after_sol,
                'trade_pct_bankroll': trade_pct_bankroll,
                'dex': swap.dex,
                'timestamp': datetime.fromtimestamp(swap.timestamp).isoformat()
            }
            
            # 5. Write to diary (single source of truth)
            await write_to_diary('trade', user_id, wallet_address, trade_data)
            logger.info(f"Wrote trade to diary: {swap.action} {token_symbol} - {trade_pct_bankroll:.2f}% of bankroll")
            
            # 6. Send trade notification first
            if app:
                try:
                    # Format using the NotificationEngine
                    trade_msg = await self.notification_engine.format_enriched_notification(
                        swap,
                        wallet_name=f"{wallet_address[:4]}...{wallet_address[-4:]}"
                    )
                    
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=trade_msg,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    logger.info("Trade notification sent")
                except Exception as e:
                    logger.error(f"Error sending trade notification: {e}")
            
            # 7. Get GPT response with new lean system
            try:
                # Build minimal prompt
                prompt_data = await build_prompt(user_id, wallet_address, 'trade', trade_data)
                
                # Load Coach L prompt
                with open('coach_prompt_v1.md', 'r') as f:
                    coach_prompt = f.read()
                
                # Get GPT response with tools
                response = await self.gpt_client.chat_with_tools(
                    system_prompt=coach_prompt,
                    user_message=json.dumps(prompt_data),
                    tools=self._get_gpt_tools()
                )
                
                if response:
                    # Write response to diary
                    await write_to_diary('response', user_id, wallet_address, {'text': response})
                    
                    # Send GPT response
                    await asyncio.sleep(1)  # Brief pause after trade notification
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=response
                    )
                    logger.info(f"Sent GPT response: '{response[:50]}...'")
                    
            except Exception as e:
                logger.error(f"Error generating GPT response: {e}")
            
        except Exception as e:
            logger.error(f"Error processing swap: {e}")
    
    def _get_gpt_tools(self):
        """Get tool definitions for GPT"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "fetch_last_n_trades",
                    "description": "Get user's recent trades",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "n": {"type": "integer", "description": "Number of trades to fetch"}
                        },
                        "required": ["n"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_trades_by_token",
                    "description": "Get trades for specific token",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "token": {"type": "string", "description": "Token symbol"},
                            "n": {"type": "integer", "description": "Number of trades"}
                        },
                        "required": ["token"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_trades_by_time",
                    "description": "Get trades within hour range (e.g., 2-6 for late night)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_hour": {"type": "integer", "description": "Start hour (0-23)"},
                            "end_hour": {"type": "integer", "description": "End hour (0-23)"},
                            "n": {"type": "integer", "description": "Number of trades"}
                        },
                        "required": ["start_hour", "end_hour"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_token_balance",
                    "description": "Get current balance for a token",
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "token": {"type": "string", "description": "Token symbol"}
                        },
                        "required": ["token"]
                    }
                }
            }
        ]
    
    async def _init_monitoring_on_startup(self):
        """Restart monitoring for all active users on bot startup"""
        db = duckdb.connect(self.db_path)
        try:
            # Get all active connections
            active_users = db.execute("""
                SELECT user_id, wallet_address
                FROM user_wallets
                WHERE is_active = TRUE
            """).fetchall()
            
            for user_id, wallet_address in active_users:
                await self._start_monitoring_for_user(user_id, wallet_address)
                logger.info(f"Restarted monitoring for user {user_id}")
            
            logger.info(f"Restarted monitoring for {len(active_users)} users")
            
        except Exception as e:
            logger.error(f"Error initializing monitoring: {e}")
        finally:
            db.close()
    
    def run(self):
        """Run the bot"""
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Store application reference for monitoring tasks
        self.application = application
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("connect", self.connect_command))
        application.add_handler(CommandHandler("disconnect", self.disconnect_command))
        application.add_handler(CommandHandler("note", self.note_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        
        # Add conversational handlers
        application.add_handler(CallbackQueryHandler(self.handle_note_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        
        # Initialize monitoring on startup
        async def post_init(app):
            await self._init_monitoring_on_startup()
        
        application.post_init = post_init
        
        # Start the bot
        logger.info("Starting Pocket Trading Coach bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main entry point"""
    import signal
    import sys
    
    # Define PID file path
    PID_FILE = "telegram_bot_coach.pid"
    
    # Check if another instance is running
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            os.kill(pid, 0)  # This will raise an exception if process doesn't exist
            
            logger.error(f"Bot is already running with PID {pid}. Use 'kill {pid}' to stop it.")
            return
            
        except (ProcessLookupError, ValueError):
            # Process doesn't exist or PID file is corrupted, remove it
            logger.info("Removing stale PID file")
            os.remove(PID_FILE)
    
    # Write current PID to file
    pid = os.getpid()
    with open(PID_FILE, 'w') as f:
        f.write(str(pid))
    logger.info(f"Starting bot with PID {pid}")
    
    def cleanup_and_exit(signum, frame):
        """Clean up PID file and exit gracefully"""
        logger.info("Shutting down bot...")
        
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        sys.exit(0)
    
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)
    
    try:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not set")
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
            return
        
        bot = PocketCoachBot(token)
        bot.run()
        
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        raise
    finally:
        # Clean up PID file if we exit normally
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

if __name__ == "__main__":
    main() 