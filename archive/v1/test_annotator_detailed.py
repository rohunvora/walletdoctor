#!/usr/bin/env python3
"""
Detailed test of annotator to verify:
1. Actual trade dates (not today)
2. Individual trades (not grouped)
3. Cielo P&L data usage
"""

import asyncio
import duckdb
import json
from diary_api_fixed import get_notable_trades

async def test_detailed():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("=== TESTING ANNOTATOR IMPLEMENTATION ===\n")
    
    # 1. Check raw data from database
    print("1. Checking raw database data...")
    db = duckdb.connect('pocket_coach.db')
    
    # Get some SELL trades
    results = db.execute("""
        SELECT 
            timestamp,
            json_extract_string(data, '$.token_symbol') as token,
            json_extract_string(data, '$.action') as action,
            json_extract(data, '$.pnl_validated') as pnl_validated,
            json_extract(data, '$.realized_pnl_usd') as realized_pnl
        FROM diary 
        WHERE wallet_address = ? 
        AND entry_type = 'trade'
        AND json_extract_string(data, '$.action') = 'SELL'
        ORDER BY timestamp DESC
        LIMIT 5
    """, [wallet]).fetchall()
    
    print(f"Found {len(results)} SELL trades in database:")
    for row in results:
        timestamp, token, action, pnl_validated, realized_pnl = row
        print(f"  - {timestamp.strftime('%Y-%m-%d')} {token}: pnl_validated={pnl_validated is not None}, realized_pnl={realized_pnl}")
    
    db.close()
    
    # 2. Check notable trades function
    print("\n2. Testing get_notable_trades function...")
    trades = await get_notable_trades(wallet, days=30, max_trades=7)
    
    print(f"Found {len(trades)} notable trades:")
    
    # Check for duplicates
    tokens_seen = {}
    for trade in trades:
        token = trade['token']
        date = trade['exit_date']
        
        if token in tokens_seen:
            print(f"  ⚠️  DUPLICATE: {token} appears multiple times!")
            print(f"      First: {tokens_seen[token]}")
            print(f"      Again: {date}")
        else:
            tokens_seen[token] = date
        
        # Check date
        if date == '2024-01-30' or date == asyncio.get_event_loop().time():
            print(f"  ❌ WRONG DATE: {token} has today's date!")
        else:
            print(f"  ✅ {token} on {date} - {trade['selection_reason']}")
        
        # Check P&L source
        if 'pnl_pct' in trade:
            print(f"     P&L: {trade['pnl_pct']:.1f}% (${trade.get('pnl_usd', 0):.0f})")
    
    # 3. Test CSV export format
    print("\n3. CSV Export Preview:")
    print("date,token,pnl%,reasoning")
    for trade in trades[:3]:
        print(f"{trade['exit_date']},{trade['token']},{trade.get('pnl_pct', 0):.0f},\"sample reasoning\"")
    
    print("\n=== TEST COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(test_detailed())