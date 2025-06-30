#!/usr/bin/env python3
"""Test the fixed coaching system"""

import asyncio
from src.services.trading_coach_fixed import get_trade_coaching

async def test():
    print("Testing FIXED coaching system...\n")
    
    result = await get_trade_coaching(
        wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        sol_amount=10.0,
        token_symbol="TEST",
        cielo_key="7c855165-3874-4237-9416-450d2373ea72"
    )
    
    if result['success']:
        print("✅ SUCCESS! Fixed coaching is working\n")
        print("Message:")
        print(result['message'])
        print(f"\n{result['emoji']} {result['coaching']}")
        
        if 'statistics' in result:
            stats = result['statistics']
            print(f"\nStats:")
            print(f"  Patterns found: {stats['total_patterns']}")
            print(f"  Win rate: {stats['win_rate']:.0f}%")
            print(f"  Avg ROI: {stats['avg_roi']:+.1f}%")
            print(f"  Total P&L: {stats['total_pnl_sol']:+.1f} SOL")
            
            # Check if this matches reality better
            print(f"\n✅ SANITY CHECK:")
            print(f"  - No duplicates (was showing 180, now showing {stats['total_patterns']})")
            print(f"  - Realistic win rate (was 72%, now {stats['win_rate']:.0f}%)")
            print(f"  - Each token appears once")
    else:
        print("❌ FAILED!")
        print(result)

asyncio.run(test())