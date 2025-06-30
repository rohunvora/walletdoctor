#!/usr/bin/env python3
"""
Backfill historical bankroll data for trades using full transaction history.

This script:
1. Fetches ALL transactions for a wallet from Helius
2. Builds a complete SOL balance timeline
3. Updates historical trades with accurate bankroll data
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
import duckdb

sys.path.append('.')
from scripts.token_balance import get_sol_balance

class BankrollBackfiller:
    def __init__(self, helius_key: str):
        self.helius_key = helius_key
        self.helius_url = f"https://api.helius.xyz/v0"
        
    async def get_all_transactions(self, wallet: str) -> List[Dict]:
        """Fetch all transactions for a wallet from Helius"""
        print(f"Fetching all transactions for {wallet}...")
        
        all_transactions = []
        before_signature = None
        
        async with aiohttp.ClientSession() as session:
            while True:
                url = f"{self.helius_url}/addresses/{wallet}/transactions"
                params = {
                    "api-key": self.helius_key,
                    "limit": 100,  # Max allowed
                    "type": "ANY"  # Get all transaction types
                }
                
                if before_signature:
                    params["before"] = before_signature
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        print(f"Error fetching transactions: {response.status}")
                        break
                        
                    data = await response.json()
                    
                    if not data:
                        break
                        
                    all_transactions.extend(data)
                    
                    # Get the last signature for pagination
                    if len(data) < 100:
                        break  # No more transactions
                    
                    before_signature = data[-1]['signature']
                    print(f"  Fetched {len(all_transactions)} transactions so far...")
        
        print(f"Total transactions fetched: {len(all_transactions)}")
        return all_transactions
    
    def extract_sol_changes(self, transaction: Dict, wallet: str) -> float:
        """Extract SOL balance change from a transaction"""
        sol_change = 0.0
        
        # Check native balance changes
        if 'nativeBalanceChange' in transaction:
            sol_change = transaction['nativeBalanceChange'] / 1e9  # Convert lamports to SOL
            
        # Also check accountData for more complex transactions
        if 'accountData' in transaction:
            for account in transaction['accountData']:
                if account['account'] == wallet:
                    if 'nativeBalanceChange' in account:
                        sol_change = account['nativeBalanceChange'] / 1e9
                        
        return sol_change
    
    def build_balance_timeline(self, transactions: List[Dict], wallet: str, current_balance: float) -> Dict[int, float]:
        """Build a timeline of SOL balances from transactions"""
        print("Building balance timeline...")
        
        # Sort transactions by timestamp (oldest first)
        sorted_txs = sorted(transactions, key=lambda x: x['timestamp'])
        
        # Start from current balance and work backwards
        balance_timeline = {}
        balance = current_balance
        
        # Process from newest to oldest to reconstruct historical balances
        for tx in reversed(sorted_txs):
            timestamp = tx['timestamp']
            sol_change = self.extract_sol_changes(tx, wallet)
            
            # Record balance AFTER this transaction
            balance_timeline[timestamp] = balance
            
            # Subtract the change to get balance BEFORE this transaction
            balance -= sol_change
            
        print(f"Timeline built with {len(balance_timeline)} data points")
        print(f"Earliest balance: {balance:.4f} SOL")
        print(f"Latest balance: {current_balance:.4f} SOL")
        
        return balance_timeline
    
    def get_balance_at_timestamp(self, timeline: Dict[int, float], timestamp: int) -> Optional[float]:
        """Get SOL balance at a specific timestamp"""
        # Find the closest timestamp before or at the requested time
        applicable_timestamps = [ts for ts in timeline.keys() if ts <= timestamp]
        
        if not applicable_timestamps:
            return None
            
        closest_timestamp = max(applicable_timestamps)
        return timeline[closest_timestamp]
    
    async def backfill_wallet(self, wallet: str):
        """Backfill bankroll data for all trades from a wallet"""
        print(f"\n{'='*60}")
        print(f"Backfilling bankroll data for wallet: {wallet}")
        print('='*60)
        
        # Step 1: Get current balance
        current_balance = await get_sol_balance(wallet)
        print(f"\nCurrent SOL balance: {current_balance:.4f}")
        
        # Step 2: Get all transactions
        transactions = await self.get_all_transactions(wallet)
        
        if not transactions:
            print("No transactions found!")
            return
            
        # Step 3: Build balance timeline
        timeline = self.build_balance_timeline(transactions, wallet, current_balance)
        
        # Step 4: Get trades from diary that need backfilling
        conn = duckdb.connect('pocket_coach.db')
        
        # Find trades without bankroll data
        query = """
            SELECT id, wallet_address, timestamp, action, sol_amount, 
                   token_symbol, bankroll_before_sol
            FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND action IN ('buy', 'sell')
            AND bankroll_before_sol IS NULL
            ORDER BY timestamp DESC
        """
        
        trades = conn.execute(query, [wallet]).fetchall()
        print(f"\nFound {len(trades)} trades without bankroll data")
        
        if not trades:
            print("No trades need backfilling!")
            conn.close()
            return
            
        # Step 5: Update each trade
        updates = []
        for trade in trades:
            trade_id, wallet_addr, timestamp_str, action, sol_amount, token_symbol, _ = trade
            
            # Parse timestamp
            timestamp_dt = datetime.fromisoformat(timestamp_str)
            timestamp_unix = int(timestamp_dt.timestamp())
            
            # Get balance at trade time
            balance_at_trade = self.get_balance_at_timestamp(timeline, timestamp_unix)
            
            if balance_at_trade is None:
                print(f"  ⚠️  No balance data for {token_symbol} trade at {timestamp_str}")
                continue
                
            # Calculate bankroll values
            if action == 'buy':
                bankroll_before = balance_at_trade + sol_amount  # Add back what was spent
                bankroll_after = balance_at_trade
                trade_pct = (sol_amount / bankroll_before * 100) if bankroll_before > 0 else 0
            else:  # sell
                bankroll_before = balance_at_trade - sol_amount  # Subtract what was received
                bankroll_after = balance_at_trade
                trade_pct = None  # Not applicable for sells
                
            updates.append({
                'id': trade_id,
                'bankroll_before_sol': bankroll_before,
                'bankroll_after_sol': bankroll_after,
                'trade_pct_bankroll': trade_pct
            })
            
            print(f"  ✅ {timestamp_str} - {action.upper()} {token_symbol}: "
                  f"bankroll {bankroll_before:.2f} → {bankroll_after:.2f} SOL"
                  f"{f' ({trade_pct:.1f}%)' if trade_pct else ''}")
        
        # Step 6: Apply updates
        if updates:
            print(f"\nApplying {len(updates)} updates...")
            
            for update in updates:
                update_query = """
                    UPDATE diary 
                    SET bankroll_before_sol = ?,
                        bankroll_after_sol = ?,
                        trade_pct_bankroll = ?
                    WHERE id = ?
                """
                conn.execute(update_query, [
                    update['bankroll_before_sol'],
                    update['bankroll_after_sol'],
                    update['trade_pct_bankroll'],
                    update['id']
                ])
            
            conn.commit()
            print("✅ Backfill complete!")
        
        conn.close()

async def main():
    """Backfill bankroll data for specified wallets"""
    
    helius_key = os.getenv('HELIUS_KEY')
    if not helius_key:
        print("❌ HELIUS_KEY not found in environment")
        return
        
    backfiller = BankrollBackfiller(helius_key)
    
    # Test wallets
    wallets = [
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",  # Your wallet
        # Add more wallets as needed
    ]
    
    for wallet in wallets:
        await backfiller.backfill_wallet(wallet)
        
    print("\n✅ All backfills complete!")

if __name__ == "__main__":
    asyncio.run(main())