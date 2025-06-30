#!/usr/bin/env python3
"""
Monitoring Manager - Coordinates real-time wallet monitoring
"""

import asyncio
import logging
import os
import duckdb
from typing import Dict, Set
from datetime import datetime
from .wallet_monitor import SolanaWalletMonitor
from .transaction_parser import TransactionParser, SwapTransaction
from .notification_engine import NotificationEngine

logger = logging.getLogger(__name__)

class MonitoringManager:
    def __init__(self, db_path: str, bot_token: str):
        self.db_path = db_path
        self.bot_token = bot_token
        self.monitor = SolanaWalletMonitor()
        self.parser = TransactionParser()
        self.notifier = NotificationEngine()
        self.monitoring_task = None
        self.is_running = False
        self.monitored_wallets: Dict[str, Dict] = {}  # wallet_address -> user_info
        
    async def start_monitoring(self):
        """Start the background monitoring process"""
        if self.is_running:
            logger.info("Monitoring already running")
            return
            
        logger.info("🔍 Starting wallet monitoring manager...")
        
        # Load monitored wallets from database
        await self._load_monitored_wallets()
        
        if not self.monitored_wallets:
            logger.info("No wallets to monitor, waiting for additions...")
        else:
            logger.info(f"Loaded {len(self.monitored_wallets)} wallets to monitor")
        
        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.is_running = True
        
    async def stop_monitoring(self):
        """Stop the monitoring process"""
        self.is_running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        await self.monitor.disconnect()
        logger.info("🔕 Monitoring stopped")
        
    async def add_wallet_monitoring(self, user_id: int, wallet_address: str, wallet_name: str = None):
        """Add a new wallet to monitoring"""
        self.monitored_wallets[wallet_address] = {
            'user_id': user_id,
            'wallet_name': wallet_name,
            'added_at': datetime.now()
        }
        
        logger.info(f"➕ Added wallet {wallet_address[:8]}... for user {user_id} to polling monitor")
        
    async def remove_wallet_monitoring(self, wallet_address: str):
        """Remove a wallet from monitoring"""
        if wallet_address in self.monitored_wallets:
            del self.monitored_wallets[wallet_address]
            logger.info(f"➖ Removed wallet {wallet_address[:8]}... from monitoring")
    
    async def _load_monitored_wallets(self):
        """Load monitored wallets from database"""
        try:
            db = duckdb.connect(self.db_path)
            
            wallets = db.execute("""
                SELECT user_id, wallet_address, wallet_name 
                FROM monitored_wallets 
                WHERE is_active = TRUE
            """).fetchall()
            
            for user_id, wallet_address, wallet_name in wallets:
                self.monitored_wallets[wallet_address] = {
                    'user_id': user_id,
                    'wallet_name': wallet_name,
                    'added_at': datetime.now()
                }
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error loading monitored wallets: {e}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop - simplified polling approach"""
        logger.info("🔄 Starting polling-based monitoring loop...")
        
        while self.is_running:
            try:
                if not self.monitored_wallets:
                    # No wallets to monitor, sleep and check again
                    await asyncio.sleep(30)
                    await self._load_monitored_wallets()  # Reload from DB
                    continue
                
                # Check each monitored wallet for recent transactions
                for wallet_address in list(self.monitored_wallets.keys()):
                    try:
                        logger.info(f"🔍 Checking wallet {wallet_address[:8]}... for recent swaps")
                        recent_swaps = await self._check_recent_swaps(wallet_address, limit=5)
                        
                        for swap in recent_swaps:
                            await self._process_swap_notification(swap)
                            
                    except Exception as e:
                        logger.error(f"Error checking wallet {wallet_address}: {e}")
                
                # Wait before next check
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _handle_transaction(self, wallet_address: str, transaction_data: dict):
        """Handle a transaction notification"""
        try:
            logger.info(f"🔔 Transaction detected for wallet {wallet_address}")
            
            # For now, we'll implement a simpler approach using recent transactions
            # The WebSocket notifications are complex, so let's poll recent transactions
            recent_swaps = await self._check_recent_swaps(wallet_address)
            
            for swap in recent_swaps:
                await self._process_swap_notification(swap)
                
        except Exception as e:
            logger.error(f"Error handling transaction for {wallet_address}: {e}")
    
    async def _check_recent_swaps(self, wallet_address: str, limit: int = 5):
        """Check for recent swap transactions (polling approach)"""
        try:
            # Get recent transactions
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
                async with session.post(self.parser.rpc_url, json=payload) as response:
                    result = await response.json()
                    signatures = result.get("result", [])
            
            logger.info(f"Found {len(signatures)} recent transactions for {wallet_address[:8]}...")
            
            # Parse each transaction
            swaps = []
            for tx_info in signatures:
                signature = tx_info["signature"]
                
                # Check if we've already processed this transaction
                if await self._is_transaction_processed(signature):
                    logger.debug(f"Transaction {signature[:16]}... already processed")
                    continue
                
                logger.info(f"Parsing transaction {signature[:16]}...")
                swap = await self.parser.parse_transaction(signature)
                if swap:
                    logger.info(f"🎯 Detected swap: {swap.action} {swap.amount_in} {swap.token_in[:8]}... for {swap.amount_out} {swap.token_out[:8]}... on {swap.dex}")
                    swaps.append(swap)
                    await self._mark_transaction_processed(swap)
                else:
                    logger.debug(f"Transaction {signature[:16]}... is not a swap")
            
            if swaps:
                logger.info(f"Found {len(swaps)} new swaps to notify")
            
            return swaps
            
        except Exception as e:
            logger.error(f"Error checking recent swaps: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def _is_transaction_processed(self, signature: str) -> bool:
        """Check if transaction has already been processed"""
        try:
            db = duckdb.connect(self.db_path)
            result = db.execute(
                "SELECT 1 FROM wallet_transactions WHERE tx_signature = ?",
                [signature]
            ).fetchone()
            db.close()
            return result is not None
        except:
            return False
    
    async def _mark_transaction_processed(self, swap: SwapTransaction):
        """Mark transaction as processed in database"""
        try:
            db = duckdb.connect(self.db_path)
            # DuckDB uses INSERT OR REPLACE, not IGNORE
            db.execute("""
                INSERT OR REPLACE INTO wallet_transactions 
                (tx_signature, wallet_address, timestamp, action, token_in, token_out, 
                 amount_in, amount_out, dex, program_id, slot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                swap.signature, swap.wallet_address, swap.timestamp, swap.action,
                swap.token_in, swap.token_out, swap.amount_in, swap.amount_out,
                swap.dex, swap.program_id, swap.slot
            ])
            db.close()
        except Exception as e:
            logger.error(f"Error marking transaction processed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _process_swap_notification(self, swap: SwapTransaction):
        """Process and send swap notification"""
        try:
            wallet_info = self.monitored_wallets.get(swap.wallet_address)
            if not wallet_info:
                return
            
            # Format notification with enriched data
            wallet_name = wallet_info['wallet_name']
            try:
                message = await self.notifier.format_enriched_notification(swap, wallet_name)
            except Exception as e:
                logger.warning(f"Failed to create enriched notification, falling back to basic: {e}")
                message = self.notifier.format_basic_swap_notification(swap, wallet_name)
            
            # Send to user with HTML parse mode for clickable links
            user_id = wallet_info['user_id']
            success = await self.notifier.send_notification(message, user_id, self.bot_token)
            
            if success:
                logger.info(f"✅ Notification sent for {swap.action} {swap.dex} transaction")
            else:
                logger.error(f"❌ Failed to send notification for transaction {swap.signature}")
                
        except Exception as e:
            logger.error(f"Error processing swap notification: {e}")
            import traceback
            logger.error(traceback.format_exc())

# Global monitoring manager instance
_monitoring_manager = None

async def get_monitoring_manager(db_path: str, bot_token: str) -> MonitoringManager:
    """Get or create the global monitoring manager"""
    global _monitoring_manager
    if _monitoring_manager is None:
        _monitoring_manager = MonitoringManager(db_path, bot_token)
        await _monitoring_manager.start_monitoring()
    return _monitoring_manager 