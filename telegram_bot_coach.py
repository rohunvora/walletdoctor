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

# Import new conversational components
from nudge_engine import create_nudge_engine
from pattern_service import create_pattern_service
from conversation_manager import create_conversation_manager
from metrics_collector import create_metrics_collector

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
        
        # Initialize conversational components with DB path for fresh connections
        nudge_config = {
            "text_first_mode": True,
            "openai_api_key": os.getenv("OPENAI_API_KEY")  # Use environment variable
        }
        self.nudge_engine = create_nudge_engine("rules", config=nudge_config)
        self.pattern_service = create_pattern_service(db_path=self.db_path, pnl_service=self.pnl_service)
        self.conversation_manager = create_conversation_manager(db_path=self.db_path)
        self.metrics_collector = create_metrics_collector(None)
        
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
            
            # Clear pending context
            self.conversation_manager.clear_pending_response(user_id)
            
            # Track skip
            self.metrics_collector.record_response(
                user_id,
                'unknown',
                'skip',
                0
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
                # Store button response (shouldn't happen in text-first mode)
                metadata = {
                    'response_type': 'button',
                    'pattern_type': 'unknown',
                    'token_symbol': 'unknown',
                    'timestamp': datetime.now().isoformat()
                }
                
                success = await self.conversation_manager.store_response(
                    user_id, 
                    f"temp_{int(datetime.now().timestamp())}",
                    response_type.replace('_', ' '),
                    metadata
                )
                
                if success:
                    await query.edit_message_text(
                        text=query.message.text + f"\n\n✅ Got it: '{response_type.replace('_', ' ')}' 📝",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        text=query.message.text + "\n\n❌ Error saving response. Try again.",
                        parse_mode='Markdown'
                    )
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text responses in text-first mode"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        logger.info(f"Received text message from user {user_id}: '{message_text}'")
        
        # Check if user has pending response
        pending_context = self.conversation_manager.get_pending_response(user_id)
        
        # If no pending context, check if this is a response to a recent nudge
        if not pending_context:
            logger.info(f"No pending context for user {user_id}, checking recent trades")
            # Get the most recent trade context for this user (within last 2 minutes)
            db = duckdb.connect(self.db_path)
            try:
                result = db.execute("""
                    SELECT tx_signature, token_address, token_symbol, action
                    FROM user_trades
                    WHERE user_id = ?
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '2 minutes'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, [user_id]).fetchone()
                
                if result:
                    logger.info(f"Found recent trade for user {user_id}: {result[0][:8]}...")
                    # Create context from recent trade
                    pending_context = {
                        'trade_id': result[0],
                        'token_address': result[1],
                        'token_symbol': result[2],
                        'pattern_data': {'action': result[3], 'token_symbol': result[2]}
                    }
                else:
                    logger.info(f"No recent trades found for user {user_id}")
            except Exception as e:
                logger.error(f"Error querying recent trades: {e}")
            finally:
                db.close()
        
        if pending_context:
            logger.info(f"Processing response for trade {pending_context.get('trade_id', 'unknown')[:8]}...")
            
            # Skip privacy notice - it's annoying
            
            # Show typing indicator
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            
            # Extract tag using GPT
            tag_info = await self.nudge_engine.extract_tag_from_text(
                message_text,
                pending_context
            )
            
            # Store the response with extracted tag
            metadata = {
                'response_type': 'text',
                'pattern_type': pending_context.get('pattern_type', 'unknown'),
                'token_symbol': pending_context.get('token_symbol', 'unknown'),
                'token_address': pending_context.get('token_address'),
                'timestamp': datetime.now().isoformat(),
                'tag': tag_info['tag'],
                'tag_confidence': tag_info['confidence'],
                'tag_method': tag_info['method'],
                'tag_latency': tag_info['latency']
            }
            
            success = await self.conversation_manager.store_response(
                user_id,
                pending_context['trade_id'],
                message_text,
                metadata
            )
            
            if success:
                # Format and send the tag response
                response_text = self.nudge_engine.format_tag_response(tag_info)
                await update.message.reply_text(response_text, parse_mode='Markdown')
                
                # Log metrics
                logger.info(f"Tagged response: '{tag_info['tag']}' via {tag_info['method']} in {tag_info['latency']:.2f}s")
                
                # Track metrics
                self.metrics_collector.record_response(
                    user_id,
                    pending_context.get('pattern_type', 'unknown'),
                    'text',
                    tag_info['latency']
                )
            else:
                logger.error(f"Failed to store response for user {user_id}")
                await update.message.reply_text("❌ Error saving response. Try again.")
                
            # Clear pending context
            self.conversation_manager.clear_pending_response(user_id)
        else:
            # No context - might be a command typo or general message
            logger.info(f"Ignoring non-nudge message from user {user_id}")
            pass  # Ignore non-nudge responses
    
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
        """Process a swap transaction and generate nudges"""
        logger.info(f"Processing {swap.action} swap: {swap.signature[:8]}...")
        
        # Store transaction
        db = duckdb.connect(self.db_path)
        try:
            # Store in wallet_transactions
            db.execute("""
                INSERT INTO wallet_transactions 
                (tx_signature, wallet_address, timestamp, action, token_in, token_out, 
                 amount_in, amount_out, dex, program_id, slot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tx_signature) DO NOTHING
            """, [
                swap.signature,
                wallet_address,
                swap.timestamp,
                swap.action,
                swap.token_in,
                swap.token_out,
                swap.amount_in,
                swap.amount_out,
                swap.dex,
                swap.program_id,
                swap.slot
            ])
            
            # Determine token info based on action
            if swap.action == 'BUY':
                token_address = swap.token_out
                sol_amount = swap.amount_in  # Already in SOL units
            else:  # SELL
                token_address = swap.token_in
                sol_amount = swap.amount_out  # Already in SOL units
            
            # Get token metadata
            token_metadata = await self.token_metadata_service.get_token_metadata(token_address)
            token_symbol = token_metadata.symbol if token_metadata else 'Unknown'
            
            # Store in user_trades (simplified for now)
            try:
                db.execute("""
                    INSERT INTO user_trades
                    (user_id, wallet_address, tx_signature, timestamp, action, 
                     token_address, token_symbol, sol_amount, token_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    user_id,
                    wallet_address,
                    swap.signature,
                    datetime.fromtimestamp(swap.timestamp),
                    swap.action,
                    token_address,
                    token_symbol,
                    sol_amount,
                    swap.amount_out if swap.action == 'BUY' else swap.amount_in
                ])
                logger.info(f"Stored trade: {swap.action} {token_symbol} - {sol_amount:.4f} SOL")
            except Exception as e:
                logger.error(f"Error storing trade: {e}")
            
            db.commit()
            
            # Generate conversational nudges using new architecture
            logger.info(f"Starting pattern detection for {swap.action} {token_symbol}")
            trade_context = {
                "user_id": user_id,
                "wallet_address": wallet_address,
                "token_address": token_address,
                "token_symbol": token_symbol,
                "sol_amount": sol_amount,
                "action": swap.action,
                "timestamp": datetime.fromtimestamp(swap.timestamp)
            }
            
            # Detect patterns using new service
            logger.info(f"Calling pattern service with context: {trade_context}")
            patterns = await self.pattern_service.detect(trade_context)
            logger.info(f"Pattern detection returned {len(patterns)} patterns: {[p['type'] for p in patterns]}")
            
            # Generate questions for each pattern
            questions = []
            for pattern in patterns[:1]:  # Limit to most important pattern
                logger.info(f"Processing pattern: {pattern['type']} with confidence {pattern['confidence']}")
                # Get memory for this pattern/token
                previous_response = await self.conversation_manager.get_last_response(
                    user_id, 
                    token_address if pattern['type'] == 'repeat_token' else None,
                    pattern['type']
                )
                logger.info(f"Retrieved previous response: {previous_response}")
                
                # Generate question with memory
                context = {
                    "pattern_type": pattern['type'],
                    "pattern_data": pattern['data'],
                    "user_history": {},
                    "previous_response": previous_response
                }
                
                logger.info(f"Generating nudge with context: {context}")
                question, keyboard = self.nudge_engine.get_nudge(context)
                logger.info(f"Generated question: '{question}' with keyboard: {keyboard is not None}")
                if question:  # Only check if question exists, keyboard is optional in text-first mode
                    questions.append((question, keyboard, pattern))
            
            # Send trade notification first using rich format
            if app:
                try:
                    logger.info(f"Generating trade notification for {swap.action} {token_symbol}")
                    # Format using the NotificationEngine
                    trade_msg = await self.notification_engine.format_enriched_notification(
                        swap,
                        wallet_name=f"{wallet_address[:4]}...{wallet_address[-4:]}"
                    )
                    
                    logger.info(f"Sending trade notification: {len(trade_msg)} chars")
                    # Send trade notification  
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=trade_msg,
                        parse_mode='HTML',  # NotificationEngine uses HTML format
                        disable_web_page_preview=True
                    )
                    logger.info("Trade notification sent successfully")
                except Exception as e:
                    logger.error(f"Error sending trade notification: {e}")
            
            # Send conversational questions after a short delay
            logger.info(f"Generated {len(questions)} questions total")
            if questions and app:
                await asyncio.sleep(1)  # Brief pause between messages
                for question, keyboard, pattern in questions[:1]:  # Send only the most relevant question
                    try:
                        logger.info(f"Sending conversational question: '{question}'")
                        # Store the context for this question
                        question_context = {
                            'trade_id': swap.signature,
                            'pattern_type': pattern['type'],
                            'token_address': token_address,
                            'token_symbol': token_symbol,
                            'pattern_data': pattern['data']
                        }
                        
                        # Store as pending response for text-first mode
                        self.conversation_manager.set_pending_response(user_id, question_context)
                        
                        # Send question with inline keyboard
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=question,
                            reply_markup=keyboard,
                            parse_mode='Markdown'
                        )
                        
                        logger.info(f"Sent conversational question for {pattern['type']} pattern")
                        
                    except Exception as e:
                        logger.error(f"Error sending question: {e}")
            else:
                logger.info(f"No questions to send. questions={len(questions)}, app={app is not None}")
            
        except Exception as e:
            logger.error(f"Error processing transaction: {e}")
        finally:
            db.close()
    
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
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    
    bot = PocketCoachBot(token)
    bot.run()

if __name__ == "__main__":
    main() 