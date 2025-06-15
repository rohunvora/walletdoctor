#!/usr/bin/env python3
"""
Tradebro Monitoring Service - Watches wallets and alerts on pattern matches
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
import duckdb
from telegram import Bot
from typing import Dict, List, Set
from scripts.data import load_wallet
from scripts.instant_stats import InstantStatsGenerator

logger = logging.getLogger(__name__)

class WalletMonitor:
    def __init__(self, token: str, db_path: str = "coach.db"):
        self.bot = Bot(token=token)
        self.db_path = db_path
        self.check_interval = 120  # 2 minutes
        self.last_check_time = {}  # Track per-wallet last check
        self.known_trades = {}  # Track trades we've already seen
        
    async def check_wallet(self, user_id: int, wallet_address: str):
        """Check a wallet for new trades"""
        try:
            db = duckdb.connect(self.db_path)
            
            # Get user's patterns
            patterns = db.execute("""
                SELECT DISTINCT annotation 
                FROM telegram_annotations 
                WHERE user_id = ?
            """, [user_id]).fetchall()
            
            # Load latest wallet data
            success = load_wallet(db, wallet_address, mode='instant')
            if not success:
                return
                
            # Get recent trades (last 24 hours)
            recent_trades = db.execute("""
                SELECT symbol, realizedPnl, timestamp 
                FROM trades 
                WHERE wallet = ? 
                AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, [wallet_address, datetime.now() - timedelta(days=1)]).fetchall()
            
            # Check for new trades
            wallet_key = f"{user_id}_{wallet_address}"
            if wallet_key not in self.known_trades:
                self.known_trades[wallet_key] = set()
                
            for trade in recent_trades:
                trade_id = f"{trade[0]}_{trade[2]}"  # symbol_timestamp
                
                if trade_id not in self.known_trades[wallet_key]:
                    self.known_trades[wallet_key].add(trade_id)
                    
                    # Check if this matches any patterns
                    await self.check_patterns(user_id, trade, patterns)
                    
            db.close()
            
        except Exception as e:
            logger.error(f"Error checking wallet {wallet_address}: {e}")
            
    async def check_patterns(self, user_id: int, trade, patterns):
        """Check if a trade matches user's documented patterns"""
        symbol, pnl, timestamp = trade
        
        # Skip if profitable
        if pnl > 0:
            return
            
        # Check each pattern
        alerts = []
        for pattern in patterns:
            pattern_text = pattern[0].lower()
            
            # Pattern matching rules
            if "fomo" in pattern_text and abs(pnl) > 1000:
                alerts.append(f"⚠️ FOMO Pattern Detected!")
                
            if "revenge" in pattern_text and abs(pnl) > 500:
                alerts.append(f"🔴 Revenge Trading Pattern!")
                
            if "twitter" in pattern_text or "influencer" in pattern_text:
                alerts.append(f"📱 Social Media FOMO Pattern!")
                
            if "late" in pattern_text or "pump" in pattern_text:
                alerts.append(f"📈 Late Entry Pattern!")
                
        if alerts:
            message = (
                f"🚨 *Pattern Alert for {symbol}*\n\n"
                f"Loss: ${abs(pnl):,.0f}\n\n"
            )
            
            for alert in alerts[:2]:  # Max 2 alerts
                message += f"{alert}\n"
                
            message += (
                f"\n💭 _Remember your past mistakes:_\n"
                f"This matches patterns you've documented before.\n\n"
                f"Take a breath. Is this trade different?"
            )
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            
    async def run_monitoring_loop(self, monitored_wallets: Dict[int, str]):
        """Main monitoring loop"""
        logger.info("Starting wallet monitoring...")
        
        while True:
            try:
                for user_id, wallet in monitored_wallets.items():
                    await self.check_wallet(user_id, wallet)
                    
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if TOKEN:
        monitor = WalletMonitor(TOKEN)
        
        # Example: Monitor a wallet
        test_wallets = {
            123456789: "rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK"
        }
        
        asyncio.run(monitor.run_monitoring_loop(test_wallets))
    else:
        print("Set TELEGRAM_BOT_TOKEN to test monitoring") 