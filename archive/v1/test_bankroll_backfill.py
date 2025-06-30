#!/usr/bin/env python3

import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
import json

sys.path.append('.')
import os
os.environ['HELIUS_KEY'] = os.getenv('HELIUS_KEY', '')

from diary_api import get_all_trades_for_wallet, get_trades_in_range
from scripts.token_balance import get_sol_balance
import duckdb

async def test_bankroll_backfill():
    """Test the bankroll backfill approach with real data"""
    
    print("=== BANKROLL BACKFILL TEST ===")
    print("Testing reverse calculation approach\n")
    
    # Test wallet
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Step 1: Get current SOL balance
    print("1. Getting current SOL balance...")
    current_balance = await get_sol_balance(wallet)
    print(f"   Current balance: {current_balance:.4f} SOL")
    
    # Step 2: Get all trades from diary
    print("\n2. Fetching all trades from diary...")
    conn = duckdb.connect('pocket_coach.db', read_only=True)
    
    # Get trades ordered by timestamp DESC (newest first)
    query = """
        SELECT wallet_address, timestamp, action, sol_amount, 
               token_symbol, token_amount, token_name,
               bankroll_before_sol, bankroll_after_sol, trade_pct_bankroll
        FROM diary 
        WHERE wallet_address = ? 
        AND action IN ('buy', 'sell')
        ORDER BY timestamp DESC
    """
    
    trades = conn.execute(query, [wallet]).fetchall()
    conn.close()
    
    print(f"   Found {len(trades)} trades")
    
    # Step 3: Separate trades with and without bankroll data
    trades_with_bankroll = []
    trades_without_bankroll = []
    
    for trade in trades:
        trade_dict = {
            'wallet_address': trade[0],
            'timestamp': trade[1],
            'action': trade[2],
            'sol_amount': float(trade[3]) if trade[3] else 0,
            'token_symbol': trade[4],
            'token_amount': float(trade[5]) if trade[5] else 0,
            'token_name': trade[6],
            'bankroll_before_sol': float(trade[7]) if trade[7] else None,
            'bankroll_after_sol': float(trade[8]) if trade[8] else None,
            'trade_pct_bankroll': float(trade[9]) if trade[9] else None
        }
        
        if trade_dict['bankroll_before_sol'] is not None:
            trades_with_bankroll.append(trade_dict)
        else:
            trades_without_bankroll.append(trade_dict)
    
    print(f"   - Trades with bankroll data: {len(trades_with_bankroll)}")
    print(f"   - Trades without bankroll data: {len(trades_without_bankroll)}")
    
    # Step 4: Show recent trades with bankroll data
    if trades_with_bankroll:
        print("\n3. Recent trades WITH bankroll data:")
        print("   " + "-" * 80)
        for i, trade in enumerate(trades_with_bankroll[:5]):
            print(f"   Trade {i+1}: {trade['action'].upper()} {trade['token_symbol']}")
            print(f"     Time: {trade['timestamp']}")
            print(f"     SOL amount: {trade['sol_amount']:.4f}")
            print(f"     Bankroll before: {trade['bankroll_before_sol']:.4f} SOL")
            print(f"     Trade % of bankroll: {trade['trade_pct_bankroll']:.2f}%")
            print("   " + "-" * 80)
    
    # Step 5: Demonstrate backfill calculation
    if trades_without_bankroll:
        print("\n4. Demonstrating backfill for trades WITHOUT bankroll data:")
        print("   Starting from current balance and working backwards...\n")
        
        # Start with current balance
        calculated_balance = current_balance
        
        # First, account for all trades (with and without bankroll)
        all_trades_sorted = sorted(trades_with_bankroll + trades_without_bankroll, 
                                   key=lambda x: x['timestamp'], reverse=True)
        
        print("   Recent trades (newest to oldest):")
        print("   " + "-" * 100)
        print(f"   {'Time':<20} {'Action':<6} {'Token':<10} {'SOL':<10} {'Calc Balance':<15} {'Actual Balance':<15} {'Match':<6}")
        print("   " + "-" * 100)
        
        for i, trade in enumerate(all_trades_sorted[:20]):
            # For buys: we spent SOL, so add it back
            # For sells: we received SOL, so subtract it
            if trade['action'] == 'buy':
                calculated_balance += trade['sol_amount']
            else:  # sell
                calculated_balance -= trade['sol_amount']
            
            # Check if we have actual bankroll data to compare
            actual_balance = trade['bankroll_before_sol'] if trade['bankroll_before_sol'] else None
            match = ""
            if actual_balance:
                diff = abs(calculated_balance - actual_balance)
                match = "✓" if diff < 0.01 else f"Δ{diff:.2f}"
            
            timestamp_str = trade['timestamp'].strftime('%Y-%m-%d %H:%M')
            print(f"   {timestamp_str:<20} {trade['action']:<6} {trade['token_symbol']:<10} "
                  f"{trade['sol_amount']:<10.4f} {calculated_balance:<15.4f} "
                  f"{actual_balance if actual_balance else 'N/A':<15} {match:<6}")
    
    # Step 6: Calculate what position sizes would have been
    print("\n\n5. Calculated position sizes for historical trades:")
    print("   " + "-" * 80)
    
    calculated_balance = current_balance
    position_sizes = []
    
    for trade in all_trades_sorted[:10]:
        if trade['action'] == 'buy':
            calculated_balance += trade['sol_amount']
        else:
            calculated_balance -= trade['sol_amount']
        
        if trade['action'] == 'buy' and calculated_balance > 0:
            position_pct = (trade['sol_amount'] / calculated_balance) * 100
            position_sizes.append(position_pct)
            
            timestamp_str = trade['timestamp'].strftime('%Y-%m-%d %H:%M')
            print(f"   {timestamp_str} - {trade['token_symbol']}")
            print(f"     Spent: {trade['sol_amount']:.4f} SOL")
            print(f"     Bankroll: {calculated_balance:.4f} SOL")
            print(f"     Position size: {position_pct:.1f}% of bankroll")
            
            if trade['trade_pct_bankroll']:
                print(f"     Actual recorded: {trade['trade_pct_bankroll']:.1f}%")
            print("   " + "-" * 80)
    
    if position_sizes:
        avg_position = sum(position_sizes) / len(position_sizes)
        max_position = max(position_sizes)
        print(f"\n   Average position size: {avg_position:.1f}%")
        print(f"   Largest position: {max_position:.1f}%")
    
    print("\n\n6. Validation Notes:")
    print("   ⚠️  This approach assumes:")
    print("   - No SOL transfers in/out of wallet")
    print("   - No staking/unstaking")
    print("   - No failed transactions")
    print("   - All trades are captured in diary")
    print("\n   For production backfill, we'd need to:")
    print("   - Fetch ALL SOL transactions from Helius")
    print("   - Account for transfers, stakes, etc.")
    print("   - Build complete balance timeline")

if __name__ == "__main__":
    asyncio.run(test_bankroll_backfill())