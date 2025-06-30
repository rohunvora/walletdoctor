#!/usr/bin/env python3

import asyncio
import json
from diary_api import query_time_range, calculate_metrics, calculate_token_pnl_from_trades

async def test_mdog_analytics():
    """Test if analytics tools return accurate P&L for MDOG"""
    
    # Your wallet address (from the conversation)
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("Testing analytics accuracy for MDOG position...")
    print("=" * 60)
    
    # Test 1: Query today's trades
    print("\n1. Querying today's trades:")
    today_trades = await query_time_range(wallet, "today")
    print(f"Found {len(today_trades.get('trades', []))} trades today")
    
    # Test 2: Calculate P&L for MDOG specifically
    print("\n2. Calculating MDOG P&L:")
    mdog_pnl = await calculate_token_pnl_from_trades(wallet, "MDOG")
    print(json.dumps(mdog_pnl, indent=2))
    
    # Test 3: Calculate metrics for today
    print("\n3. Calculating today's metrics:")
    today_metrics = await calculate_metrics(wallet, "sum", "profit_sol", "today")
    print(json.dumps(today_metrics, indent=2))
    
    # Show what the bot SHOULD have said
    if 'total_pnl_usd' in mdog_pnl:
        actual_loss = mdog_pnl['total_pnl_usd']
        print(f"\n✅ CORRECT: You're down ${abs(actual_loss):.2f} on MDOG")
        print(f"❌ BOT SAID: You're down $717")
        print(f"🔍 DIFFERENCE: Bot was off by ${abs(717 - abs(actual_loss)):.2f}")

if __name__ == "__main__":
    asyncio.run(test_mdog_analytics()) 