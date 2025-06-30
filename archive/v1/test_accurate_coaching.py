#!/usr/bin/env python3
"""Test the accurate coaching system that discloses data limitations"""

import asyncio
from src.services.trading_coach_accurate import get_trade_coaching

async def test():
    print("Testing ACCURATE coaching system with full disclosure...\n")
    
    result = await get_trade_coaching(
        wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        sol_amount=10.0,
        token_symbol="TEST",
        cielo_key="7c855165-3874-4237-9416-450d2373ea72"
    )
    
    if result['success']:
        print("Message to user:")
        print("-" * 60)
        print(result['message'])
        print(f"\n{result['emoji']} {result['coaching']}")
        print("-" * 60)
        
        if 'statistics' in result:
            stats = result['statistics']
            print(f"\nInternal stats:")
            print(f"  Data complete: {stats.get('data_complete', False)}")
            print(f"  Coverage: {stats.get('coverage_percent', 0):.0f}%")
    else:
        print("❌ FAILED!")
        print(result)

asyncio.run(test())