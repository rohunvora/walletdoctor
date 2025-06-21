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

# Import price history service
from price_history_service import PriceHistoryService, PriceSnapshot

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
        self.price_monitoring_tasks = {}  # token_address -> asyncio.Task
        self.token_metadata_service = TokenMetadataService()
        self.price_service = PriceService()
        
        # Initialize P&L service
        self.pnl_service = FastPnLService(
            cielo_api_key="7c855165-3874-4237-9416-450d2373ea72",
            birdeye_api_key="4e5e878a6137491bbc280c10587a0cce"
        )
        
        # Initialize notification engine with P&L service
        self.notification_engine = NotificationEngine(pnl_service=self.pnl_service)
        
        # Initialize price history service
        self.price_history_service = PriceHistoryService(
            birdeye_api_key="4e5e878a6137491bbc280c10587a0cce",
            db_path=db_path
        )
        
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
        
        # Initialize P&L validator
        from pnl_validator import PnLValidator
        self.pnl_validator = PnLValidator()
        
        logger.info("Pocket Trading Coach initialized with lean pipeline and price history")
    
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
        
        # Price snapshots for historical tracking
        db.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                token_address TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                price_sol REAL,
                price_usd REAL,
                market_cap REAL,
                volume_24h REAL,
                liquidity_usd REAL,
                PRIMARY KEY (token_address, timestamp)
            )
        """)
        
        # Create index for efficient time-range queries
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_snapshots_token_time 
            ON price_snapshots(token_address, timestamp DESC)
        """)
        
        # User positions table for tracking holdings and peaks
        db.execute("""
            CREATE TABLE IF NOT EXISTS user_positions (
                user_id BIGINT NOT NULL,
                wallet_address TEXT NOT NULL,
                token_address TEXT NOT NULL,
                token_symbol TEXT NOT NULL,
                -- Position details
                token_balance REAL DEFAULT 0,
                avg_entry_price_sol REAL,
                avg_entry_price_usd REAL,
                avg_entry_market_cap REAL,
                total_invested_sol REAL DEFAULT 0,
                total_invested_usd REAL DEFAULT 0,
                -- Peak tracking
                peak_price_sol REAL,
                peak_price_usd REAL,
                peak_market_cap REAL,
                peak_timestamp TIMESTAMP,
                peak_multiplier_from_entry REAL,
                -- Position metadata
                first_buy_timestamp TIMESTAMP,
                last_buy_timestamp TIMESTAMP,
                last_update_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                -- Primary key
                PRIMARY KEY (user_id, token_address)
            )
        """)
        
        # Create indexes for efficient queries
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_positions_wallet 
            ON user_positions(wallet_address, is_active)
        """)
        
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_positions_token 
            ON user_positions(token_address, is_active)
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
    
    async def _get_transaction_balances(self, signature: str, wallet_address: str) -> Optional[Dict[str, float]]:
        """Get pre and post SOL balances from a transaction"""
        try:
            import aiohttp
            helius_key = os.getenv('HELIUS_KEY')
            rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_key}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {
                        "encoding": "json",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(rpc_url, json=payload) as response:
                    result = await response.json()
                    
                    if 'result' not in result or not result['result']:
                        logger.error(f"No transaction data found for {signature}")
                        return None
                    
                    tx_data = result['result']
                    meta = tx_data.get('meta', {})
                    
                    # Get account keys
                    account_keys = tx_data.get('transaction', {}).get('message', {}).get('accountKeys', [])
                    
                    # Find wallet index
                    wallet_index = None
                    for i, key in enumerate(account_keys):
                        if key == wallet_address:
                            wallet_index = i
                            break
                    
                    if wallet_index is None:
                        logger.error(f"Wallet {wallet_address} not found in transaction")
                        return None
                    
                    # Get pre and post balances in lamports
                    pre_balances = meta.get('preBalances', [])
                    post_balances = meta.get('postBalances', [])
                    
                    if wallet_index >= len(pre_balances) or wallet_index >= len(post_balances):
                        logger.error(f"Balance index out of range")
                        return None
                    
                    # Convert lamports to SOL
                    pre_sol = pre_balances[wallet_index] / 1_000_000_000
                    post_sol = post_balances[wallet_index] / 1_000_000_000
                    
                    return {
                        'pre_sol_balance': pre_sol,
                        'post_sol_balance': post_sol
                    }
                    
        except Exception as e:
            logger.error(f"Error fetching transaction balances: {e}")
            return None
    
    async def _get_last_buy_trade(self, wallet_address: str, token_symbol: str) -> Optional[Dict]:
        """Get the most recent BUY trade for a token to find entry market cap"""
        import json
        db = duckdb.connect(self.db_path)
        try:
            result = db.execute("""
                SELECT data 
                FROM diary 
                WHERE wallet_address = ? 
                AND entry_type = 'trade'
                AND json_extract_string(data, '$.action') = 'BUY'
                AND json_extract_string(data, '$.token_symbol') = ?
                ORDER BY timestamp DESC 
                LIMIT 1
            """, [wallet_address, token_symbol]).fetchone()
            
            return json.loads(result[0]) if result else None
        finally:
            db.close()
    
    async def _estimate_entry_market_cap(self, token_address: str, avg_buy_price: float, 
                                       current_price: float, current_mcap: float) -> Optional[float]:
        """Estimate market cap at average entry price based on price ratio"""
        try:
            if current_price > 0 and avg_buy_price > 0 and current_mcap > 0:
                # Market cap scales linearly with price for most tokens
                # mcap = price * circulating_supply, so if supply is constant:
                # entry_mcap / current_mcap = avg_buy_price / current_price
                price_ratio = avg_buy_price / current_price
                estimated_entry_mcap = current_mcap * price_ratio
                
                logger.info(f"Estimated entry mcap: ${estimated_entry_mcap:,.0f} "
                          f"(avg buy ${avg_buy_price:.6f}, current ${current_price:.6f})")
                
                return estimated_entry_mcap
            return None
        except Exception as e:
            logger.error(f"Error estimating entry market cap: {e}")
            return None
    
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
            # 1. Get bankroll from transaction pre/post balances
            # First get the actual balance changes from the transaction
            pre_post_balances = await self._get_transaction_balances(swap.signature, wallet_address)
            
            if pre_post_balances:
                bankroll_before_sol = pre_post_balances['pre_sol_balance']
                bankroll_after_sol = pre_post_balances['post_sol_balance']
                logger.info(f"From transaction - Bankroll before: {bankroll_before_sol:.4f} SOL, after: {bankroll_after_sol:.4f} SOL")
            else:
                # Fallback to current balance if we can't get transaction balances
                logger.warning("Could not get pre/post balances from transaction, using current balance")
                current_balance = await self._get_sol_balance(wallet_address)
                # For BUY, add back what was spent. For SELL, subtract what was received
                if swap.action == 'BUY':
                    bankroll_before_sol = current_balance + swap.amount_in  # Add back SOL spent
                    bankroll_after_sol = current_balance
                else:  # SELL
                    bankroll_before_sol = current_balance - swap.amount_out  # Subtract SOL received
                    bankroll_after_sol = current_balance
                logger.info(f"Estimated - Bankroll before: {bankroll_before_sol:.4f} SOL, after: {bankroll_after_sol:.4f} SOL")
            
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
            
            # Get market cap at trade time
            market_cap = await self.token_metadata_service.get_market_cap(token_address)
            market_cap_formatted = self.token_metadata_service.format_market_cap(market_cap)
            logger.info(f"Market cap at {swap.action}: {market_cap_formatted}")
            
            # 3. Start price monitoring for this token (if not already monitoring)
            await self.start_price_monitoring(token_address, token_symbol)
            
            # 4. Fetch current price snapshot for position tracking
            price_snapshot = await self.price_history_service.fetch_and_store_price_data(
                token_address, token_symbol
            )
            
            # 5. Update user position
            if swap.action == 'BUY' and price_snapshot:
                await self._update_position_on_buy(
                    user_id, wallet_address, token_address, token_symbol,
                    token_amount, sol_amount, price_snapshot
                )
            elif swap.action == 'SELL':
                await self._update_position_on_sell(
                    user_id, wallet_address, token_address, token_amount
                )
            
            # 6. Bankroll after is already set from transaction data above
            
            # Calculate exact percentage (no rounding as per requirement)
            trade_pct_bankroll = (sol_amount / bankroll_before_sol) * 100 if bankroll_before_sol > 0 else 0
            
            # Log the calculation for debugging
            logger.info(f"Trade percentage calculation: {sol_amount:.4f} SOL / {bankroll_before_sol:.4f} SOL = {trade_pct_bankroll:.2f}%")
            
            # 7. Prepare complete trade data for diary
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
                'timestamp': datetime.fromtimestamp(swap.timestamp).isoformat(),
                'market_cap': market_cap,
                'market_cap_formatted': market_cap_formatted
            }
            
            # Add price per token for better tracking (especially for DCA scenarios)
            if token_amount > 0:
                trade_data['price_per_token'] = sol_amount / token_amount
                logger.info(f"Price per token: {trade_data['price_per_token']:.8f} SOL")
            
            # Add SOL price for USD context
            try:
                sol_price_usd = await self.pnl_service.get_sol_price()
                trade_data['sol_price_usd'] = sol_price_usd
                trade_data['trade_size_usd'] = sol_amount * sol_price_usd
                logger.info(f"Trade size: {sol_amount:.3f} SOL (${trade_data['trade_size_usd']:.2f} USD)")
            except Exception as e:
                logger.error(f"Error fetching SOL price: {e}")
            
            # 8.5 For SELL trades, fetch P&L data from Cielo and entry market cap
            if swap.action == 'SELL':
                try:
                    # Get P&L data from Cielo
                    pnl_data = await self.pnl_service.get_token_pnl_data(
                        wallet_address, 
                        token_address
                    )
                    
                    if pnl_data:
                        # Add P&L fields to diary entry
                        trade_data['realized_pnl_usd'] = pnl_data.get('realized_pnl_usd', 0)
                        trade_data['total_pnl_usd'] = pnl_data.get('total_pnl_usd', 0)
                        trade_data['unrealized_pnl_usd'] = pnl_data.get('unrealized_pnl_usd', 0)
                        trade_data['avg_buy_price'] = pnl_data.get('avg_buy_price', 0)
                        trade_data['avg_sell_price'] = pnl_data.get('avg_sell_price', 0)
                        trade_data['roi_percentage'] = pnl_data.get('roi_percentage', 0)
                        trade_data['num_swaps'] = pnl_data.get('total_trades', 0)
                        trade_data['hold_time_seconds'] = pnl_data.get('holding_time_seconds', 0)
                        
                        # Validate and reconcile P&L data
                        validated_pnl = self.pnl_validator.validate_and_reconcile_pnl(trade_data)
                        
                        # Use validated P&L for logging
                        logger.info(f"Validated P&L: {validated_pnl['explanation']}")
                        
                        # Add validation results to trade data
                        trade_data['pnl_validated'] = validated_pnl
                        trade_data['pnl_has_issues'] = validated_pnl.get('has_issues', False)
                        
                except Exception as e:
                    logger.error(f"Error fetching P&L data: {e}")
                    # Continue without P&L data rather than failing
                
                # Calculate average entry market cap using Cielo's average buy price
                try:
                    if 'avg_buy_price' in trade_data and trade_data['avg_buy_price'] > 0:
                        # IMPORTANT: Use the ACTUAL price of this trade, not Cielo's avg_sell_price
                        # which is the average of ALL historical sells
                        current_price_sol = sol_amount / token_amount if token_amount > 0 else 0
                        
                        # Convert current price to USD to match avg_buy_price units
                        sol_price_usd = trade_data.get('sol_price_usd', 175.0)  # Use fetched SOL price or default
                        current_price_usd = current_price_sol * sol_price_usd
                        
                        # Estimate market cap at average entry price
                        entry_mcap = await self._estimate_entry_market_cap(
                            token_address,
                            trade_data['avg_buy_price'],
                            current_price_usd,
                            market_cap
                        )
                        
                        if entry_mcap:
                            trade_data['entry_market_cap'] = entry_mcap
                            trade_data['entry_market_cap_formatted'] = self.token_metadata_service.format_market_cap(entry_mcap)
                            trade_data['market_cap_multiplier'] = market_cap / entry_mcap
                            
                            logger.info(f"Market cap multiplier: {trade_data['market_cap_multiplier']:.2f}x "
                                      f"(from {trade_data['entry_market_cap_formatted']} avg entry to {market_cap_formatted})")
                    else:
                        # Fallback to last buy if no average price from Cielo
                        logger.info("No average buy price from Cielo, falling back to last buy trade")
                        last_buy = await self._get_last_buy_trade(wallet_address, token_symbol)
                        if last_buy and 'market_cap' in last_buy:
                            entry_mcap = last_buy['market_cap']
                            trade_data['entry_market_cap'] = entry_mcap
                            trade_data['entry_market_cap_formatted'] = self.token_metadata_service.format_market_cap(entry_mcap)
                            trade_data['market_cap_multiplier'] = market_cap / entry_mcap
                            
                except Exception as e:
                    logger.error(f"Error calculating entry market cap: {e}")
            
            # 9. Write to diary (single source of truth)
            await write_to_diary('trade', user_id, wallet_address, trade_data)
            logger.info(f"Wrote trade to diary: {swap.action} {token_symbol} - {trade_pct_bankroll:.2f}% of bankroll")
            
            # 10. Send market cap-centric trade notification
            if app:
                try:
                    # Create market cap-centric notification
                    if swap.action == 'BUY':
                        # Format: "🟢 Bought BONK at $1.2M mcap (0.5 SOL)"
                        trade_msg = f"🟢 Bought {token_symbol} at {market_cap_formatted} mcap ({sol_amount:.3f} SOL)"
                    else:  # SELL
                        # Include entry mcap and multiplier if available
                        if 'market_cap_multiplier' in trade_data and trade_data['market_cap_multiplier']:
                            # Format: "🔴 Sold WIF at $5.4M mcap (2.7x from $2M avg entry) +$230"
                            pnl_str = ""
                            if 'realized_pnl_usd' in trade_data:
                                pnl = trade_data['realized_pnl_usd']
                                pnl_str = f" {'+' if pnl >= 0 else ''}${abs(pnl):.0f}"
                            
                            # Check if this is from average of multiple buys
                            avg_indicator = " avg" if trade_data.get('num_swaps', 0) > 1 else ""
                            
                            # Format multiplier better - show 2 decimals if less than 1x
                            multiplier = trade_data['market_cap_multiplier']
                            if multiplier < 1:
                                multiplier_str = f"{multiplier:.2f}x"
                            else:
                                multiplier_str = f"{multiplier:.1f}x"
                            
                            trade_msg = f"🔴 Sold {token_symbol} at {market_cap_formatted} mcap ({multiplier_str} from {trade_data.get('entry_market_cap_formatted', 'unknown')}{avg_indicator} entry){pnl_str}"
                        else:
                            # No entry mcap data
                            trade_msg = f"🔴 Sold {token_symbol} at {market_cap_formatted} mcap ({sol_amount:.3f} SOL)"
                    
                    # Add the notification engine's full format as a second message for now
                    # This preserves all the rich data while we transition to mcap-centric
                    full_msg = await self.notification_engine.format_enriched_notification(
                        swap,
                        wallet_name=f"{wallet_address[:4]}...{wallet_address[-4:]}"
                    )
                    
                    # Send market cap focused message first
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=trade_msg,
                        parse_mode='Markdown'
                    )
                    
                    # Then send full notification
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=full_msg,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    logger.info("Market cap-centric notification sent")
                except Exception as e:
                    logger.error(f"Error sending trade notification: {e}")
            
            # 11. Get GPT response with new lean system
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
                    tools=self._get_gpt_tools(),
                    wallet_address=wallet_address  # Pass wallet for tool execution
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
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_wallet_stats",
                    "description": "Get overall trading statistics for the wallet including win rate, total P&L, and trade count",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_token_pnl",
                    "description": "Get P&L data for a specific token including realized/unrealized gains",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "token": {"type": "string", "description": "Token symbol to get P&L for"}
                        },
                        "required": ["token"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_market_cap_context",
                    "description": "Get market cap context for a token including entry mcap, current mcap, multiplier, and risk analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "token": {"type": "string", "description": "Token symbol to analyze"}
                        },
                        "required": ["token"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_price_context",
                    "description": "Get comprehensive price context including 1h/24h changes, peak data, and token age",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "token": {"type": "string", "description": "Token symbol to get price context for"}
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
            
            # Also restart price monitoring for all active positions
            active_positions = db.execute("""
                SELECT DISTINCT token_address, token_symbol
                FROM user_positions
                WHERE is_active = TRUE
            """).fetchall()
            
            for token_address, token_symbol in active_positions:
                await self.start_price_monitoring(token_address, token_symbol)
            
            logger.info(f"Restarted price monitoring for {len(active_positions)} tokens")
            
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
        application.add_handler(CommandHandler("watch", self.watch_command))
        
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

    async def update_user_position_peak(self, user_id: int, wallet_address: str, 
                                      token_address: str, current_snapshot: PriceSnapshot):
        """Update user position with peak tracking"""
        db = duckdb.connect(self.db_path)
        try:
            # Get current position
            result = db.execute("""
                SELECT peak_price_sol, peak_price_usd, peak_market_cap,
                       avg_entry_price_sol, avg_entry_price_usd, avg_entry_market_cap,
                       token_symbol
                FROM user_positions
                WHERE user_id = ? AND token_address = ? AND is_active = TRUE
            """, [user_id, token_address]).fetchone()
            
            if not result:
                logger.debug(f"No active position found for user {user_id} token {token_address}")
                return
            
            peak_price_sol, peak_price_usd, peak_market_cap, \
            avg_entry_sol, avg_entry_usd, avg_entry_mcap, token_symbol = result
            
            # Check if new peak
            peak_updated = False
            new_peak_multiplier = None
            
            if peak_price_usd is None or current_snapshot.price_usd > peak_price_usd:
                # New peak reached!
                peak_updated = True
                
                # Calculate multiplier from entry
                if avg_entry_usd and avg_entry_usd > 0:
                    new_peak_multiplier = current_snapshot.price_usd / avg_entry_usd
                
                # Update peak values
                db.execute("""
                    UPDATE user_positions
                    SET peak_price_sol = ?,
                        peak_price_usd = ?,
                        peak_market_cap = ?,
                        peak_timestamp = ?,
                        peak_multiplier_from_entry = ?,
                        last_update_timestamp = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND token_address = ?
                """, [
                    current_snapshot.price_sol,
                    current_snapshot.price_usd,
                    current_snapshot.market_cap,
                    current_snapshot.timestamp,
                    new_peak_multiplier,
                    user_id,
                    token_address
                ])
                db.commit()
                
                # Check for milestone alerts (3x, 5x, 10x)
                if new_peak_multiplier:
                    await self._check_peak_alerts(user_id, token_symbol, new_peak_multiplier)
                    
            logger.debug(f"Position update for {token_symbol}: peak_updated={peak_updated}, multiplier={new_peak_multiplier}")
            
        except Exception as e:
            logger.error(f"Error updating user position peak: {e}")
        finally:
            db.close()
    
    async def _check_peak_alerts(self, user_id: int, token_symbol: str, multiplier: float):
        """Send alerts for peak milestones"""
        # Define milestones
        milestones = [3, 5, 10, 20, 50, 100]
        
        # Find which milestone was just crossed
        for milestone in milestones:
            if multiplier >= milestone and multiplier < milestone * 1.1:  # Just crossed
                alert_msg = f"🚀 **{token_symbol} hit {milestone}x from your entry!**\n\n"
                alert_msg += f"Consider taking some profits to lock in gains."
                
                try:
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=alert_msg,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Sent {milestone}x peak alert for {token_symbol} to user {user_id}")
                except Exception as e:
                    logger.error(f"Error sending peak alert: {e}")
                break
    
    async def _monitor_token_prices(self, token_address: str, token_symbol: str):
        """Monitor prices for a specific token every minute"""
        logger.info(f"Starting price monitoring for {token_symbol} ({token_address})")
        
        while True:
            try:
                # Fetch and store current price
                snapshot = await self.price_history_service.fetch_and_store_price_data(
                    token_address, token_symbol
                )
                
                if snapshot:
                    # Update peaks for all users holding this token
                    db = duckdb.connect(self.db_path)
                    try:
                        # Get all users with active positions in this token
                        users = db.execute("""
                            SELECT DISTINCT user_id, wallet_address
                            FROM user_positions
                            WHERE token_address = ? AND is_active = TRUE
                        """, [token_address]).fetchall()
                        
                        # Update each user's position
                        for user_id, wallet_address in users:
                            await self.update_user_position_peak(
                                user_id, wallet_address, token_address, snapshot
                            )
                            
                    except Exception as e:
                        logger.error(f"Error updating user positions: {e}")
                    finally:
                        db.close()
                        
                    logger.debug(f"Price update for {token_symbol}: ${snapshot.price_usd:.8f}")
                else:
                    logger.warning(f"Failed to fetch price for {token_symbol}")
                
                # Wait 1 minute before next check
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info(f"Price monitoring stopped for {token_symbol}")
                break
            except Exception as e:
                logger.error(f"Error in price monitoring for {token_symbol}: {e}")
                await asyncio.sleep(60)  # Still wait to avoid rapid retries
    
    async def start_price_monitoring(self, token_address: str, token_symbol: str):
        """Start monitoring a token's price if not already monitoring"""
        if token_address not in self.price_monitoring_tasks:
            task = asyncio.create_task(
                self._monitor_token_prices(token_address, token_symbol)
            )
            self.price_monitoring_tasks[token_address] = task
            logger.info(f"Started price monitoring for {token_symbol}")
    
    async def watch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually add a token to watch list"""
        if not context.args:
            await update.message.reply_text(
                "Usage: `/watch <token_address>`\n\n"
                "Example:\n"
                "`/watch DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`",
                parse_mode='Markdown'
            )
            return
        
        token_address = context.args[0]
        user_id = update.effective_user.id
        
        # Validate token address format
        if len(token_address) < 32 or len(token_address) > 44:
            await update.message.reply_text("❌ Invalid token address format")
            return
        
        # Get token metadata
        metadata = await self.token_metadata_service.get_token_metadata(token_address)
        token_symbol = metadata.symbol if metadata else "Unknown"
        
        # Start monitoring
        await self.start_price_monitoring(token_address, token_symbol)
        
        # Fetch initial price data
        snapshot = await self.price_history_service.fetch_and_store_price_data(
            token_address, token_symbol
        )
        
        if snapshot:
            msg = f"✅ Now tracking **{token_symbol}**\n\n"
            msg += f"💰 Price: ${snapshot.price_usd:.8f}\n"
            msg += f"📊 Market Cap: ${snapshot.market_cap:,.0f}\n"
            msg += f"💧 Liquidity: ${snapshot.liquidity_usd:,.0f}\n\n"
            msg += "Price updates every minute. Peak alerts enabled."
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"✅ Watching {token_symbol}, but couldn't fetch initial price data. "
                "Will retry in 1 minute."
            )

    async def _update_position_on_buy(self, user_id: int, wallet_address: str,
                                    token_address: str, token_symbol: str,
                                    token_amount: float, sol_amount: float,
                                    price_snapshot: PriceSnapshot):
        """Update or create user position on buy"""
        db = duckdb.connect(self.db_path)
        try:
            # Check if position exists
            result = db.execute("""
                SELECT token_balance, total_invested_sol, total_invested_usd,
                       avg_entry_price_sol, avg_entry_price_usd
                FROM user_positions
                WHERE user_id = ? AND token_address = ?
            """, [user_id, token_address]).fetchone()
            
            if result:
                # Update existing position (DCA)
                old_balance, old_invested_sol, old_invested_usd, _, _ = result
                
                new_balance = old_balance + token_amount
                new_invested_sol = old_invested_sol + sol_amount
                new_invested_usd = old_invested_usd + (sol_amount * price_snapshot.price_usd / price_snapshot.price_sol)
                
                # Calculate new average prices
                avg_entry_price_sol = new_invested_sol / new_balance if new_balance > 0 else 0
                avg_entry_price_usd = new_invested_usd / new_balance if new_balance > 0 else 0
                
                # Estimate average entry market cap
                if price_snapshot.price_usd > 0:
                    price_ratio = avg_entry_price_usd / price_snapshot.price_usd
                    avg_entry_market_cap = price_snapshot.market_cap * price_ratio
                else:
                    avg_entry_market_cap = price_snapshot.market_cap
                
                db.execute("""
                    UPDATE user_positions
                    SET token_balance = ?,
                        total_invested_sol = ?,
                        total_invested_usd = ?,
                        avg_entry_price_sol = ?,
                        avg_entry_price_usd = ?,
                        avg_entry_market_cap = ?,
                        last_buy_timestamp = CURRENT_TIMESTAMP,
                        last_update_timestamp = CURRENT_TIMESTAMP,
                        is_active = TRUE
                    WHERE user_id = ? AND token_address = ?
                """, [
                    new_balance, new_invested_sol, new_invested_usd,
                    avg_entry_price_sol, avg_entry_price_usd, avg_entry_market_cap,
                    user_id, token_address
                ])
                
            else:
                # Create new position
                db.execute("""
                    INSERT INTO user_positions (
                        user_id, wallet_address, token_address, token_symbol,
                        token_balance, avg_entry_price_sol, avg_entry_price_usd,
                        avg_entry_market_cap, total_invested_sol, total_invested_usd,
                        first_buy_timestamp, last_buy_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, [
                    user_id, wallet_address, token_address, token_symbol,
                    token_amount, 
                    sol_amount / token_amount if token_amount > 0 else 0,
                    (sol_amount * price_snapshot.price_usd / price_snapshot.price_sol) / token_amount if token_amount > 0 else 0,
                    price_snapshot.market_cap,
                    sol_amount,
                    sol_amount * price_snapshot.price_usd / price_snapshot.price_sol
                ])
            
            db.commit()
            logger.info(f"Updated position for {token_symbol}: {token_amount} tokens")
            
        except Exception as e:
            logger.error(f"Error updating position on buy: {e}")
        finally:
            db.close()
    
    async def _update_position_on_sell(self, user_id: int, wallet_address: str,
                                     token_address: str, token_amount: float):
        """Update user position on sell"""
        db = duckdb.connect(self.db_path)
        try:
            # Get current position
            result = db.execute("""
                SELECT token_balance
                FROM user_positions
                WHERE user_id = ? AND token_address = ?
            """, [user_id, token_address]).fetchone()
            
            if result:
                old_balance = result[0]
                new_balance = max(0, old_balance - token_amount)
                
                if new_balance < 0.0001:  # Essentially zero
                    # Mark position as inactive
                    db.execute("""
                        UPDATE user_positions
                        SET token_balance = 0,
                            is_active = FALSE,
                            last_update_timestamp = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND token_address = ?
                    """, [user_id, token_address])
                else:
                    # Update balance
                    db.execute("""
                        UPDATE user_positions
                        SET token_balance = ?,
                            last_update_timestamp = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND token_address = ?
                    """, [new_balance, user_id, token_address])
                
                db.commit()
                logger.info(f"Updated position after sell: {new_balance} tokens remaining")
                
        except Exception as e:
            logger.error(f"Error updating position on sell: {e}")
        finally:
            db.close()

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