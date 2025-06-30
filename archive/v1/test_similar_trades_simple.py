#!/usr/bin/env python3
"""Test similar trades functionality with simpler approach"""

import sys
sys.path.append('.')
import duckdb
import json

def test_similar_trades():
    """Test finding similar trades"""
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    conn = duckdb.connect('pocket_coach.db', read_only=True)
    
    # First, let's see what trades we have
    print("=== CHECKING RECENT TRADES ===")
    
    recent_trades = conn.execute("""
        SELECT 
            timestamp,
            json_extract_string(data, '$.token_symbol') as token,
            json_extract_string(data, '$.action') as action,
            CAST(json_extract_string(data, '$.sol_amount') AS DOUBLE) as sol_amount,
            CAST(json_extract_string(data, '$.market_cap') AS DOUBLE) as market_cap
        FROM diary
        WHERE wallet_address = ?
        AND entry_type = 'trade'
        AND json_extract_string(data, '$.action') = 'BUY'  -- uppercase
        ORDER BY timestamp DESC
        LIMIT 10
    """, [wallet]).fetchall()
    
    print(f"Found {len(recent_trades)} recent buy trades:")
    for trade in recent_trades:
        timestamp, token, action, sol_amount, market_cap = trade
        print(f"  {timestamp} - {token}: {sol_amount:.2f} SOL @ ${market_cap/1e6:.2f}M mcap")
    
    if not recent_trades:
        print("No trades found!")
        return
        
    # Now test finding similar trades
    print("\n=== TESTING SIMILAR TRADE FINDER ===")
    
    # Use the most recent trade as reference
    ref_trade = recent_trades[0]
    ref_mcap = ref_trade[4]
    ref_sol = ref_trade[3]
    
    print(f"\nReference trade: {ref_trade[1]} - {ref_sol:.2f} SOL @ ${ref_mcap/1e6:.2f}M")
    print(f"Looking for trades with:")
    print(f"  Market cap: ${ref_mcap*0.5/1e6:.2f}M - ${ref_mcap*1.5/1e6:.2f}M")
    print(f"  SOL amount: {ref_sol*0.7:.2f} - {ref_sol*1.3:.2f} SOL")
    
    # Find similar trades
    similar = conn.execute("""
        WITH trade_data AS (
            SELECT 
                timestamp,
                json_extract_string(data, '$.token_symbol') as token_symbol,
                json_extract_string(data, '$.token_address') as token_address,
                json_extract_string(data, '$.action') as action,
                CAST(json_extract_string(data, '$.sol_amount') AS DOUBLE) as sol_amount,
                CAST(json_extract_string(data, '$.market_cap') AS DOUBLE) as market_cap
            FROM diary
            WHERE wallet_address = ?
            AND entry_type = 'trade'
        ),
        buy_trades AS (
            SELECT * FROM trade_data
            WHERE action = 'BUY'
            AND market_cap BETWEEN ? AND ?
            AND sol_amount BETWEEN ? AND ?
            AND token_symbol != ?
        )
        SELECT 
            token_symbol,
            sol_amount,
            market_cap,
            timestamp
        FROM buy_trades
        ORDER BY timestamp DESC
        LIMIT 5
    """, [
        wallet,
        ref_mcap * 0.5, ref_mcap * 1.5,
        ref_sol * 0.7, ref_sol * 1.3,
        ref_trade[1]  # Exclude reference token
    ]).fetchall()
    
    print(f"\nFound {len(similar)} similar trades:")
    for trade in similar:
        token, sol_amt, mcap, ts = trade
        print(f"  {ts} - {token}: {sol_amt:.2f} SOL @ ${mcap/1e6:.2f}M")
    
    # Now check P&L for these trades
    print("\n=== CHECKING P&L OUTCOMES ===")
    
    for trade in similar[:3]:
        token = trade[0]
        buy_sol = trade[1]
        
        # Find sells for this token
        sells = conn.execute("""
            SELECT 
                SUM(CAST(json_extract_string(data, '$.sol_amount') AS DOUBLE)) as total_sold
            FROM diary
            WHERE wallet_address = ?
            AND entry_type = 'trade'
            AND json_extract_string(data, '$.action') = 'SELL'
            AND json_extract_string(data, '$.token_symbol') = ?
        """, [wallet, token]).fetchone()
        
        sold_amount = sells[0] if sells[0] else 0
        pnl = sold_amount - buy_sol
        
        print(f"\n{token}:")
        print(f"  Bought: {buy_sol:.2f} SOL")
        print(f"  Sold: {sold_amount:.2f} SOL")
        print(f"  P&L: {pnl:+.2f} SOL")
    
    conn.close()

if __name__ == "__main__":
    test_similar_trades()