#!/usr/bin/env python3
"""Test coaching with the correct API key"""

import asyncio
import sys
import os

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.trading_coach import get_trade_coaching

async def test():
    print("Testing coaching system with correct API key...\n")
    
    # Use the correct API key directly
    result = await get_trade_coaching(
        wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        sol_amount=10.0,
        token_symbol="TEST",
        cielo_key="7c855165-3874-4237-9416-450d2373ea72"  # Correct key
    )
    
    if result['success']:
        print("✅ SUCCESS! Coaching is working\n")
        print("Message:")
        print(result['message'])
        print(f"\n{result['emoji']} {result['coaching']}")
        
        if 'statistics' in result:
            stats = result['statistics']
            print(f"\nStats: {stats['total_patterns']} patterns found")
            print(f"Win rate: {stats['win_rate']:.0f}%")
            print(f"Avg ROI: {stats['avg_roi']:+.1f}%")
    else:
        print("❌ FAILED!")
        print(result)

if __name__ == "__main__":
    asyncio.run(test())