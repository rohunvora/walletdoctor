#!/usr/bin/env python3
"""Test pattern matching with real wallet data"""

import sys
sys.path.append('.')
from scripts.find_similar_trades_v2 import find_similar_trades, format_similar_trades_message, analyze_pattern_performance
import duckdb
import json

def test_real_wallet():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print(f"=== TESTING PATTERN MATCHING FOR WALLET {wallet[:8]}... ===\n")
    
    # First, let's see what kinds of trades this wallet makes
    conn = duckdb.connect('pocket_coach.db', read_only=True)
    
    # Get market cap distribution
    print("Market cap distribution of BUY trades:")
    mcap_dist = conn.execute("""
        SELECT 
            CASE 
                WHEN CAST(json_extract_string(data, '$.market_cap') AS DOUBLE) < 100000 THEN '<100K'
                WHEN CAST(json_extract_string(data, '$.market_cap') AS DOUBLE) < 500000 THEN '100K-500K'
                WHEN CAST(json_extract_string(data, '$.market_cap') AS DOUBLE) < 1000000 THEN '500K-1M'
                WHEN CAST(json_extract_string(data, '$.market_cap') AS DOUBLE) < 5000000 THEN '1M-5M'
                ELSE '>5M'
            END as mcap_range,
            COUNT(*) as count,
            AVG(CAST(json_extract_string(data, '$.sol_amount') AS DOUBLE)) as avg_sol
        FROM diary
        WHERE wallet_address = ?
        AND entry_type = 'trade'
        AND json_extract_string(data, '$.action') = 'BUY'
        GROUP BY mcap_range
        ORDER BY count DESC
    """, [wallet]).fetchall()
    
    for row in mcap_dist:
        print(f"  {row[0]}: {row[1]} trades, avg {row[2]:.1f} SOL")
    
    # Get unique tokens traded
    print("\n\nTokens traded (with P&L):")
    tokens = conn.execute("""
        WITH token_pnl AS (
            SELECT 
                json_extract_string(data, '$.token_symbol') as token,
                SUM(CASE 
                    WHEN json_extract_string(data, '$.action') = 'BUY' 
                    THEN -CAST(json_extract_string(data, '$.sol_amount') AS DOUBLE)
                    ELSE CAST(json_extract_string(data, '$.sol_amount') AS DOUBLE)
                END) as net_sol,
                COUNT(CASE WHEN json_extract_string(data, '$.action') = 'BUY' THEN 1 END) as buys,
                COUNT(CASE WHEN json_extract_string(data, '$.action') = 'SELL' THEN 1 END) as sells
            FROM diary
            WHERE wallet_address = ?
            AND entry_type = 'trade'
            GROUP BY token
        )
        SELECT token, net_sol, buys, sells
        FROM token_pnl
        ORDER BY net_sol DESC
    """, [wallet]).fetchall()
    
    for row in tokens:
        token, net_sol, buys, sells = row
        status = "CLOSED" if sells > 0 else "HOLDING"
        print(f"  {token}: {net_sol:+.2f} SOL ({buys} buys, {sells} sells) - {status}")
    
    # Now test pattern matching for different scenarios
    print("\n\n=== PATTERN MATCHING TESTS ===")
    
    # Test 1: Small position at low mcap (like the MOCHI trade)
    print("\nTest 1: Small position at low mcap")
    print("Scenario: Buying 2 SOL of a 400K mcap coin")
    
    similar = find_similar_trades(
        wallet_address=wallet,
        current_market_cap=400_000,
        current_sol_amount=2.0
    )
    
    if similar:
        print(f"Found {len(similar)} similar trades:")
        for trade in similar[:3]:
            print(f"  {trade['token_symbol']} @ {trade['entry_mcap_formatted']}: "
                  f"{trade['initial_sol']:.1f} SOL → "
                  f"{trade['pnl_sol']:+.1f} SOL" if trade['pnl_sol'] is not None else "holding")
        
        analysis = analyze_pattern_performance(similar)
        if analysis and 'win_rate' in analysis:
            print(f"\nPattern analysis:")
            print(f"  Win rate: {analysis['win_rate']*100:.0f}%")
            print(f"  Avg P&L: {analysis['avg_pnl_sol']:+.1f} SOL")
    else:
        print("No similar trades found")
    
    # Test 2: Larger position (like YOURSELF trades)
    print("\n\nTest 2: Larger position")
    print("Scenario: Buying 20 SOL of a 1.5M mcap coin")
    
    similar = find_similar_trades(
        wallet_address=wallet,
        current_market_cap=1_500_000,
        current_sol_amount=20.0
    )
    
    if similar:
        print(f"Found {len(similar)} similar trades:")
        message = format_similar_trades_message(similar)
        print(f"Bot message format: {message}")
    else:
        print("No similar trades found")
    
    # Test 3: Most common pattern
    print("\n\nTest 3: Your most common trade pattern")
    print("Scenario: Buying 4 SOL of a 300K mcap coin")
    
    similar = find_similar_trades(
        wallet_address=wallet,
        current_market_cap=300_000,
        current_sol_amount=4.0
    )
    
    if similar:
        print(f"Found {len(similar)} similar trades")
        analysis = analyze_pattern_performance(similar)
        print(f"Formatted message: {format_similar_trades_message(similar)}")
        
        # Show what the bot would say
        print(f"\nBot would say:")
        print(f"\"last {len(similar)} times you bought ~300K coins with ~4 SOL: "
              f"{format_similar_trades_message(similar)}. what's the thesis?\"")
    else:
        print("No similar trades found")
    
    conn.close()

if __name__ == "__main__":
    test_real_wallet()